#!/usr/bin/env python3
#
# Copyright Red Hat
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

import logging
import re
from typing import Any
from urllib.parse import urlparse

import requests
from attrs import converters, define, field
from prometheus_client import Counter

import pelorus
from failure.collector_base import (
    AbstractFailureCollector,
    FailureProviderAuthenticationError,
    TrackerIssue,
    issue_parse_failures,
)
from pelorus.config import env_var_names, env_vars
from pelorus.config.converters import comma_or_whitespace_separated
from pelorus.config.log import REDACT, log
from pelorus.utils import TokenAuth, set_up_requests_session
from provider_common.github import parse_datetime

_github_api_errors = Counter(
    "pelorus_failure_github_api_errors_total",
    "Total GitHub API errors during failure issue collection",
)

DEFAULT_GITHUB_ISSUE_LABEL = "bug"

_SAFE_PROJECT_NAME = re.compile(r"^[A-Za-z0-9_./-]+$")


@define(kw_only=True)
class GitHubFailureCollector(AbstractFailureCollector):
    """GitHub implementation of a FailureCollector."""

    token: str = field(
        default="",
        metadata=env_vars(*env_var_names.TOKEN) | log(REDACT),
        repr=False,
    )

    tracker_api: str = field(
        default="api.github.com", metadata=env_vars("SERVER")
    )

    projects: set[str] = field(
        factory=set, converter=comma_or_whitespace_separated(set)
    )

    tls_verify: bool = field(default=pelorus.DEFAULT_TLS_VERIFY, converter=converters.to_bool)

    session: requests.Session = field(factory=requests.Session, init=False)

    issue_label: str = field(
        default=DEFAULT_GITHUB_ISSUE_LABEL, metadata=env_vars("GITHUB_ISSUE_LABEL")
    )

    _PAGE_SIZE = 100
    _ACCEPT_HEADERS = {"Accept": "application/vnd.github.v3+json"}

    def __attrs_post_init__(self):
        # Strip scheme if provided — tracker_api is used as a hostname in URL templates
        parsed = urlparse(self.tracker_api)
        if parsed.scheme in ("http", "https") and parsed.hostname:
            self.tracker_api = parsed.hostname
            if parsed.port:
                self.tracker_api += f":{parsed.port}"
        if not self.tracker_api:
            raise ValueError("SERVER must not be empty")

        for p in self.projects:
            if not _SAFE_PROJECT_NAME.match(p) or ".." in p:
                raise ValueError(f"Invalid project name: {p!r}")

        if self.token:
            set_up_requests_session(
                self.session, self.tls_verify, auth=TokenAuth(self.token)
            )

        try:
            self._get_github_user()
        except Exception:
            logging.error(
                "GitHub authentication failed (api=%s). Verify TOKEN is valid.",
                self.tracker_api,
                exc_info=True,
            )
            raise

    def _get_github_user(self) -> str:
        url = f"https://{self.tracker_api}/user"
        resp = self._make_request(None, None, url)
        if not isinstance(resp, dict) or "login" not in resp:
            raise FailureProviderAuthenticationError(
                "GitHub /user response missing 'login' field"
            )
        return resp["login"]

    def _make_request(
        self,
        headers: dict[str, str] | None,
        params: dict[str, str] | None,
        url: str,
    ) -> list | dict[str, Any]:
        resp = self.session.get(url, headers=headers, params=params, timeout=self._API_TIMEOUT)
        try:
            remaining = resp.headers.get("x-ratelimit-remaining")
            if remaining is not None:
                logging.debug("GitHub rate limit remaining: %s", remaining)
                if remaining.isdigit() and int(remaining) < 100:
                    logging.warning("GitHub rate limit low: %s remaining", remaining)
            resp.raise_for_status()
            logging.debug("GitHub returned %d bytes", len(resp.text))
            return resp.json()
        except requests.JSONDecodeError:
            _github_api_errors.inc()
            logging.error("Invalid JSON response from GitHub: %s", url, exc_info=True)
            raise
        except requests.HTTPError as e:
            _github_api_errors.inc()
            if resp.status_code == requests.codes.unauthorized:
                logging.error("GitHub auth failed (url=%s)", url, exc_info=True)
                raise FailureProviderAuthenticationError from e
            logging.error("GitHub API error %d (url=%s)", resp.status_code, url, exc_info=True)
            raise

    def get_issues(self) -> list[dict]:
        all_issues = []
        for proj in self.projects:
            logging.debug("Collecting issues from: %s", proj)
            url = f"https://{self.tracker_api}/repos/{proj}/issues"
            params = {"state": "all", "per_page": str(self._PAGE_SIZE), "labels": self.issue_label}
            page = 1

            while True:
                params["page"] = str(page)
                logging.debug("Fetching page %d for project %s", page, proj)
                issues = self._make_request(self._ACCEPT_HEADERS, params, url)
                if not isinstance(issues, list) or not issues:
                    break
                all_issues.extend(issues)
                if len(issues) < self._PAGE_SIZE:
                    break
                page += 1
            logging.debug("Collected %d total issues so far (after project %s)", len(all_issues), proj)
        return all_issues

    def search_issues(self) -> list[TrackerIssue]:
        critical_issues = []
        all_issues = self.get_issues()
        if not all_issues:
            logging.debug("No issues were found from GitHub")
            return critical_issues
        total_count = len(all_issues)

        app_label = self.app_label
        skipped = 0
        for issue in all_issues:
            try:
                labels = issue["labels"]
                label = next(
                    (label for label in labels if app_label in label["name"]), None
                )
                if not label:
                    continue

                logging.debug(
                    "Found issue opened: %s, #%s",
                    issue["created_at"], issue["number"],
                )
                created_ts = parse_datetime(issue["created_at"]).timestamp()
                resolution_ts = None
                if issue["closed_at"]:
                    logging.debug(
                        "Found issue close: %s, #%s",
                        issue["closed_at"], issue["number"],
                    )
                    resolution_ts = parse_datetime(
                        issue["closed_at"]
                    ).timestamp()
                tracker_issue = TrackerIssue(
                    str(issue["number"]),
                    created_ts,
                    resolution_ts,
                    self.get_app_name(issue, label),
                )
                critical_issues.append(tracker_issue)
            except Exception:
                skipped += 1
                issue_parse_failures.inc()
                logging.error(
                    "Failed to parse GitHub issue #%s, skipping",
                    issue.get("number", "unknown"),
                    exc_info=True,
                )
        if skipped:
            logging.warning("Skipped %d unparseable GitHub issues", skipped)
        logging.info(
            "Found %d matching issues out of %d total from GitHub",
            len(critical_issues), total_count,
        )
        return critical_issues

    def get_app_name(self, issue, label: dict[str, Any] | None):
        if label and "=" in label["name"]:
            return label["name"].split("=", 1)[1]
        repo_url = issue.get("repository_url", "")
        if repo_url:
            return repo_url.rstrip("/").split("/")[-1] or pelorus.DEFAULT_TRACKER_APP_LABEL
        return pelorus.DEFAULT_TRACKER_APP_LABEL

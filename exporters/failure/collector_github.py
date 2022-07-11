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
from datetime import datetime
from typing import Any, Optional, Union, cast

import pytz
import requests

import pelorus
from failure.collector_base import AbstractFailureCollector, TrackerIssue
from pelorus.utils import TokenAuth

# One query limit, exporter will query multiple times.
# Do not exceed 100 results
# TODO
# GITHUB_SEARCH_RESULTS = 100
# TODO Paginate results


class GithubAuthenticationError(Exception):
    """
    Exception raised for authentication issues
    """

    auth_message = "Check the TOKEN: not authorized, invalid credentials"

    def __init__(self, message=auth_message):
        super().__init__(message)


class GithubFailureCollector(AbstractFailureCollector):
    """
    Github implementation of a FailureCollector
    """

    REQUIRED_CONFIG = ["TOKEN"]
    _defaultapi = "api.github.com"

    def __init__(
        self, apikey: Optional[str], projects: str, server: Optional[str] = None
    ):
        super().__init__(server or self._defaultapi, None, apikey)

        if projects:
            self.projects = projects.split(",")
        else:
            logging.warning("No projects defined for github issues")
            self.projects = []

        self.session = requests.Session()
        # disable .netrc
        self.session.trust_env = False
        if apikey:
            self.session.auth = TokenAuth(apikey)
        try:
            self.user = self._get_github_user()
        except Exception:
            logging.warning("github username not found")
            raise

    def _get_github_user(self) -> str:
        # login and get username
        # set the username / server to env for exporter consistency
        url = "https://{}/user".format(self.server)
        resp = cast(dict[str, Any], self._make_request(None, None, url))
        return resp["login"]

    def _make_request(
        self,
        headers: Optional[dict[str, str]],
        params: Optional[dict[str, str]],
        url: str,
    ) -> Union[list, dict[str, Any]]:
        resp = self.session.get(url, headers=headers, params=params)
        try:
            resp.raise_for_status()
            logging.debug("GitHub successfully returned %s", resp.text)
            return resp.json()
        except requests.HTTPError as e:
            if resp.status_code == requests.codes.unauthorized:
                raise GithubAuthenticationError from e
            else:
                raise

    def get_issues(self) -> list[dict]:
        all_issues = []
        for proj in self.projects:
            logging.info("Getting issues from: %s", proj)
            # note: this is getting issues for each github project
            url = "https://{}/repos/{}/issues".format(self.server, proj)
            headers = {
                "Accept": "application/vnd.github.v3+json",
            }
            params = {"state": "all"}

            issues = self._make_request(headers, params, url)
            all_issues.extend(issues)
        return all_issues

    def search_issues(self) -> list[TrackerIssue]:
        critical_issues = []
        all_issues = self.get_issues()
        if not all_issues:
            logging.debug("No issues were found")
        else:
            for issue in all_issues:
                is_bug = False
                labels = issue["labels"]
                is_bug = any(label for label in labels if "bug" in label["name"])
                logging.debug(
                    "Found issue opened: {}, {}: {}".format(
                        issue["created_at"], issue["number"], issue["title"]
                    )
                )

                # Create the GithubFailureMetric
                created_ts = self.convert_timestamp(issue["created_at"])
                resolution_ts = None
                if is_bug:
                    app_label = pelorus.get_app_label()
                    label = next(
                        (label for label in labels if app_label in label["name"]), None
                    )
                    if label:
                        if issue["closed_at"]:
                            logging.debug(
                                "Found issue close: {}, {}: {}".format(
                                    issue["closed_at"], issue["number"], issue["title"]
                                )
                            )

                            resolution_ts = self.convert_timestamp(issue["closed_at"])
                        tracker_issue = TrackerIssue(
                            str(issue["number"]),
                            created_ts,
                            resolution_ts,
                            self.get_app_name(issue, label),
                        )

                        critical_issues.append(tracker_issue)
        return critical_issues

    @classmethod
    def convert_timestamp(cls, date_time):
        """Convert a Github datetime with TZ to UTC"""
        # Change the datetime to a string
        utc = datetime.strptime(date_time, "%Y-%m-%dT%H:%M:%S%z").astimezone(pytz.utc)
        # Change the datetime to a string
        utc_string = utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        # convert to timestamp
        this_date = pelorus.convert_date_time_to_timestamp(utc_string)
        # this_date is a float
        return this_date

    def get_app_name(self, issue, label: Optional[dict[str, Any]]):
        if label:
            return label["name"].split("=")[1]
        # default to repo name if app_label is not set
        else:
            return issue["repository_url"].split("/")[-1:][0]

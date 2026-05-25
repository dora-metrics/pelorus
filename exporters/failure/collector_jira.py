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
from typing import Optional

from attrs import converters, define, field
from jira import JIRA, Issue
from jira.exceptions import JIRAError

from failure.collector_base import AbstractFailureCollector, TrackerIssue, _issue_parse_failures
from pelorus.certificates import set_up_requests_certs
from pelorus.config import env_var_names, env_vars
from pelorus.config.converters import comma_or_whitespace_separated
from pelorus.config.log import REDACT, log
from pelorus.timeutil import parse_tz_aware, second_precision

_SAFE_JQL_VALUE = re.compile(r"^[A-Za-z0-9_ .-]+$")

QUERY_RESULT_FIELDS = (
    "summary,labels,created,resolutiondate,status,statuscategorychangedate"
)
DEFAULT_JQL_SEARCH_QUERY = 'type in ("Bug") AND priority in ("Highest")'
JQL_SEARCH_QUERY_ENV = "JIRA_JQL_SEARCH_QUERY"
# User specified JIRA comma separated statuses for resolved issue
RESOLVED_STATUS_ENV = "JIRA_RESOLVED_STATUS"
NON_EXISTING_PROJECT_ERROR_START = "The value '"
NON_EXISTING_PROJECT_ERROR_END = "' does not exist for the field 'project'."

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"


def remove_quotes(text: str) -> str:
    if len(text) < 2:
        return text
    if text[0] == text[-1] and text.startswith(("'", '"')):
        return text[1:-1]
    return text


@define(kw_only=True)
class JiraFailureCollector(AbstractFailureCollector):
    """JIRA implementation of a FailureCollector."""

    username: str = field(default="", metadata=env_vars(*env_var_names.USERNAME))

    token: str = field(
        default="",
        metadata=env_vars(*env_var_names.TOKEN) | log(REDACT),
        repr=False,
    )

    tracker_api: str = field(metadata=env_vars("SERVER"))

    projects: set[str] = field(
        factory=set, converter=comma_or_whitespace_separated(set)
    )

    jql_query_string: str = field(
        default=DEFAULT_JQL_SEARCH_QUERY, metadata=env_vars(JQL_SEARCH_QUERY_ENV)
    )
    tls_verify: bool = field(default=True, converter=converters.to_bool)

    jira_resolved_statuses: Optional[str] = field(
        default=None, metadata=env_vars(RESOLVED_STATUS_ENV)
    )

    # Pre-computed lowercase status list from jira_resolved_statuses
    _resolved_statuses_list: Optional[list[str]] = field(default=None, init=False)

    query_result_fields_string: str = field(default=QUERY_RESULT_FIELDS, init=False)

    app_name: Optional[str] = field(default=None, metadata=env_vars("APP_NAME"))

    _jira_client: Optional[JIRA] = field(default=None, init=False)

    # Pre-computed label prefix for app name matching
    _app_label_prefix: str = field(default="", init=False)

    def __attrs_post_init__(self):
        self._app_label_prefix = f"{self.app_label}="
        if self.jira_resolved_statuses:
            self._resolved_statuses_list = [
                status.strip().lower()
                for status in self.jira_resolved_statuses.split(",")
            ]
        # Custom JQL queries manage their own fields, so clear the default fields string
        if self.jql_query_string != DEFAULT_JQL_SEARCH_QUERY:
            self.query_result_fields_string = ""
        elif self.projects:
            for p in self.projects:
                if not _SAFE_JQL_VALUE.match(p):
                    raise ValueError(f"Invalid project name: {p!r}")
            _projects = '","'.join(self.projects)
            self.jql_query_string = (
                f'{self.jql_query_string} AND project in ("{_projects}")'
            )

    def _connect_to_jira(self) -> JIRA:
        """Connect to JIRA instance which may be cloud based or self-hosted.
        Caches the client across scrapes to avoid reconnecting each time."""
        if self._jira_client is not None:
            return self._jira_client

        try:
            # Connect to JIRA
            verify = set_up_requests_certs(self.tls_verify)
            options = {"server": self.tracker_api, "verify": verify}
            if not self.username:
                jira_client = JIRA(
                    options=options,
                    token_auth=self.token,
                )
            else:
                jira_client = JIRA(
                    options=options,
                    basic_auth=(self.username, self.token),
                )
            # Ensure connection was performed
            jira_client.session()
            self._jira_client = jira_client
            return jira_client
        except JIRAError as error:
            logging.error(
                "JIRA connection failed with status: %s", error.status_code,
                exc_info=True,
            )
            raise

    def _filter_projects_in_query_string(self, error_text: str) -> str:
        """
        Filter for only existing projects in JQL query string.

        Parameters
        ----------
        error_text : str
            Error text to get non existing projects.

        Returns
        -------
        str
            Filtered query string, if there is at least one existing project;
            else, an empty string.
        """
        non_existing_projects = {
            line.replace(NON_EXISTING_PROJECT_ERROR_START, "").replace(
                NON_EXISTING_PROJECT_ERROR_END, ""
            )
            for line in error_text.splitlines()
        }
        if self.projects:
            _projects = '","'.join(self.projects.difference(non_existing_projects))
            if _projects:
                return f'{DEFAULT_JQL_SEARCH_QUERY} AND project in ("{_projects}")'
            return ""
        matcher = "project in ("
        start_index = self.jql_query_string.find(matcher) + len(matcher)
        end_index = self.jql_query_string.find(")", start_index)
        _projects = self.jql_query_string[start_index:end_index]
        _projects_parsed = ",".join(
            {remove_quotes(project) for project in _projects.split(",")}.difference(
                non_existing_projects
            )
        )
        if _projects_parsed:
            return (
                self.jql_query_string[:start_index]
                + _projects_parsed
                + self.jql_query_string[end_index:]
            )
        return ""

    def _jql_query_issues(
        self, jira_client: JIRA, query_string: str
    ) -> list[TrackerIssue]:
        """
        Apply JQL query in JIRA instance to get issues.

        Parameters
        ----------
        jira_client : JIRA
            JIRA instance.
        query_string : str
            JQL query string.

        Returns
        -------
        list[TrackerIssue]
            List of issues.
        """
        logging.debug("JIRA JQL query: %s", query_string)
        jira_issues = jira_client.search_issues(
            query_string,
            startAt=0,
            maxResults=False,
            fields=self.query_result_fields_string,
        )

        results = []
        skipped = 0
        for issue in jira_issues:
            try:
                results.append(self._parse_issue(issue))
            except Exception:
                skipped += 1
                _issue_parse_failures.inc()
                logging.error(
                    "Failed to parse JIRA issue %s, skipping",
                    getattr(issue, "key", "unknown"),
                    exc_info=True,
                )
        if skipped:
            logging.warning("Skipped %d unparseable JIRA issues", skipped)
        return results

    def _parse_issue(self, issue: Issue) -> TrackerIssue:
        """Parse issue collected from JIRA."""
        logging.debug(issue)
        logging.debug(
            "Found issue opened: %s, %s: %s",
            issue.fields.created,
            issue.key,
            issue.fields.summary,
        )
        created_tz = parse_tz_aware(issue.fields.created, _DATETIME_FORMAT)
        created_ts = second_precision(created_tz).timestamp()
        resolution_ts = self._get_resolved_timestamp(issue, self.jira_resolved_statuses)
        return TrackerIssue(
            issue.key, created_ts, resolution_ts, self.get_app_name(issue)
        )

    def search_issues(self) -> list[TrackerIssue]:
        """
        Search for the matching issues in JIRA.

        Returns
        -------
        list[TrackerIssue]
            A list with the issues, if no error occurs; else, an empty list.
        """
        jira_client = self._connect_to_jira()
        try:
            return self._jql_query_issues(jira_client, self.jql_query_string)
        except JIRAError as error:
            if error.status_code == 400:
                logging.error(
                    "Status: %s, Error Response: %s", error.status_code, error.text,
                    exc_info=True,
                )
                if NON_EXISTING_PROJECT_ERROR_END in error.text:
                    new_query = self._filter_projects_in_query_string(error.text)
                    if new_query:
                        return self._jql_query_issues(jira_client, new_query)
                return []
            raise

    def _get_resolved_timestamp(
        self, issue: Issue, resolved_statuses: Optional[str] = None
    ) -> Optional[float]:
        """Find timestamp when the issue was resolved or moved to a status in resolved_statuses."""
        resolution_ts = None
        resolution_tz = None
        if resolved_statuses:
            # Use pre-computed list when the parameter matches the configured value
            if resolved_statuses == self.jira_resolved_statuses and self._resolved_statuses_list is not None:
                statuses = self._resolved_statuses_list
            else:
                statuses = [s.strip().lower() for s in resolved_statuses.split(",")]
            if issue.fields.status.name.lower() in statuses:
                logging.debug(
                    "Found issue %s: %s, %s: %s",
                    issue.fields.status.name,
                    issue.fields.statuscategorychangedate,
                    issue.key,
                    issue.fields.summary,
                )
                resolution_tz = parse_tz_aware(
                    issue.fields.statuscategorychangedate, _DATETIME_FORMAT
                )
        else:
            if issue.fields.resolutiondate:
                logging.debug(
                    "Found issue close: %s, %s: %s",
                    issue.fields.resolutiondate,
                    issue.key,
                    issue.fields.summary,
                )
                resolution_tz = parse_tz_aware(
                    issue.fields.resolutiondate, _DATETIME_FORMAT
                )
        if resolution_tz:
            resolution_ts = second_precision(resolution_tz).timestamp()

        return resolution_ts

    def get_app_name(self, issue: Issue) -> str:
        prefix = self._app_label_prefix
        prefix_len = len(prefix)
        for label in issue.fields.labels:
            if label.startswith(prefix):
                return label[prefix_len:]
        if self.app_name is None:
            return "unknown"
        return self.app_name

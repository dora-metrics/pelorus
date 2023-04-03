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
from typing import List, Optional

from attrs import define, field
from jira import JIRA, Issue
from jira.exceptions import JIRAError

from failure.collector_base import AbstractFailureCollector, TrackerIssue
from pelorus.config import env_var_names, env_vars
from pelorus.config.converters import comma_or_whitespace_separated
from pelorus.config.log import REDACT, log
from pelorus.timeutil import parse_tz_aware, second_precision

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
    """
    Remove surroundings single (or double) quotes from text

    Parameters
    ----------
    text : str
        Text to remove quotes from.

    Returns
    -------
    str
        text without surroundings single (or double) quotes, if it does have
        surroundings quotes; otherwise, return the text without changing it.
    """
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
    jira_resolved_statuses: Optional[str] = field(
        default=None, metadata=env_vars(RESOLVED_STATUS_ENV)
    )

    query_result_fields_string: str = field(default=QUERY_RESULT_FIELDS, init=False)

    def __attrs_post_init__(self):
        # Do not mix projects with custom JQL query
        # Gather all fields and projects
        if self.jql_query_string != DEFAULT_JQL_SEARCH_QUERY:
            self.query_result_fields_string = ""
        elif self.projects:
            _projects = '","'.join(self.projects)
            self.jql_query_string = (
                f'{self.jql_query_string} AND project in ("{_projects}")'
            )

    def _connect_to_jira(self) -> JIRA:
        """Connect to JIRA instance which may be cloud based or self-hosted."""
        try:
            # Connect to JIRA
            if not self.username:
                jira_client = JIRA(
                    options={"server": self.tracker_api},
                    token_auth=self.token,
                )
            else:
                jira_client = JIRA(
                    options={"server": self.tracker_api},
                    basic_auth=(self.username, self.token),
                )
            # Ensure connection was performed
            jira_client.session()
            return jira_client
        except JIRAError as error:
            logging.error(
                "Status: %s, Error Response: %s", error.status_code, error.text
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
    ) -> List[TrackerIssue]:
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
        List[TrackerIssue]
            List of issues.
        """
        logging.debug("JIRA JQL query: %s", query_string)
        jira_issues = jira_client.search_issues(
            query_string,
            startAt=0,
            maxResults=False,
            fields=self.query_result_fields_string,
        )

        return [self._parse_issue(issue) for issue in jira_issues]

    def _parse_issue(self, issue: Issue) -> TrackerIssue:
        """Parse issue collected from JIRA."""
        logging.debug(issue)
        logging.debug(
            "Found issue opened: %s, %s: %s",
            issue.fields.created,
            issue.key,
            issue.fields.summary,
        )
        # Create the JiraFailureMetric
        created_tz = parse_tz_aware(issue.fields.created, _DATETIME_FORMAT)
        created_ts = second_precision(created_tz).timestamp()
        resolution_ts = self._get_resolved_timestamp(issue, self.jira_resolved_statuses)
        return TrackerIssue(
            issue.key, created_ts, resolution_ts, self.get_app_name(issue)
        )

    def search_issues(self) -> List[TrackerIssue]:
        """
        Search for the matching issues in JIRA.

        Returns
        -------
        List[TrackerIssue]
            A list with the issues, if no error occurs; else, an empty list.
        """
        jira_client = self._connect_to_jira()
        try:
            return self._jql_query_issues(jira_client, self.jql_query_string)
        except JIRAError as error:
            if error.status_code == 400:
                logging.error(
                    "Status: %s, Error Response: %s", error.status_code, error.text
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
        """
        `_get_resolved_timestamp` finds timestamp when the issue was resolved or moved
        to the status that is within resolved_statuses comma separated list.
        """
        resolution_ts = None
        resolution_tz = None
        if resolved_statuses:
            statuses = [
                status.strip().lower() for status in resolved_statuses.split(",")
            ]
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
        for label in issue.fields.labels:
            matcher = f"{self.app_label}="
            if label.startswith(matcher):
                return label.replace(matcher, "")
        return "unknown"

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

import json
import os
from contextlib import nullcontext
from typing import Optional
from unittest import mock  # NOQA

import pytest
from jira.exceptions import JIRAError
from jira.resources import Issue
from prometheus_client.core import REGISTRY

from failure import collector_jira
from failure.collector_github import GithubAuthenticationError, GithubFailureCollector
from failure.collector_jira import DEFAULT_JQL_SEARCH_QUERY, JiraFailureCollector
from pelorus.config import load_and_log

JIRA_SERVER = "https://pelorustest.atlassian.net"
JIRA_USERNAME = os.environ.get("JIRA_USERNAME")
JIRA_TOKEN = os.environ.get("JIRA_TOKEN")
PROJECTS_COMMA = "proj1,proj2,proj1,proj3,proj3"
PROJECTS_SPACES = "proj1 proj2 proj1 proj3 proj3"
PROJECTS_UNIQUE = {"proj1", "proj2", "proj3"}


def setup_jira_collector(
    username: str = "fake@user.com",
    token: str = "WIEds4uZHiCGnrtmgQPn9E7D",
    projects: Optional[str] = None,
    jql_query_string: str = DEFAULT_JQL_SEARCH_QUERY,
) -> JiraFailureCollector:
    return JiraFailureCollector(
        tracker_api=JIRA_SERVER,
        username=username,
        token=token,
        projects=projects,
        jql_query_string=jql_query_string,
    )


@pytest.mark.integration
def test_jira_connection():
    collector = setup_jira_collector()
    with pytest.raises(JIRAError) as context_ex:
        collector._connect_to_jira()
    assert (
        "You are not authenticated. Authentication required to perform this operation."
        in str(context_ex.value)
    )


@pytest.mark.integration
def test_jira_pass_connection():
    collector = setup_jira_collector(token="fakepass")
    with pytest.raises(JIRAError) as context_ex:
        collector._connect_to_jira()
    assert "Basic authentication with passwords is deprecated" in str(context_ex.value)


@pytest.mark.parametrize("projects", ["non_existing,Test,wrong_name", "Test"])
@pytest.mark.integration
@pytest.mark.skipif(
    not JIRA_USERNAME, reason="No Jira username set, run export JIRA_USERNAME=username"
)
@pytest.mark.skipif(
    not JIRA_TOKEN, reason="No Jira token set, run export JIRA_TOKEN=token"
)
def test_jira_search_with_projects(projects):
    collector = setup_jira_collector(JIRA_USERNAME, JIRA_TOKEN, projects)

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 103


@pytest.mark.parametrize(
    "projects", ["non_existing,wrong_name", "project_without_issues"]
)
@pytest.mark.integration
@pytest.mark.skipif(
    not JIRA_USERNAME, reason="No Jira username set, run export JIRA_USERNAME=username"
)
@pytest.mark.skipif(
    not JIRA_TOKEN, reason="No Jira token set, run export JIRA_TOKEN=token"
)
def test_jira_search_with_projects_without_results(projects):
    collector = setup_jira_collector(JIRA_USERNAME, JIRA_TOKEN, projects)

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 0


@pytest.mark.parametrize(
    "jql",
    [
        'project in ("Test","wrong_name") AND type in ("Bug") AND priority in ("Highest")',
        "type in (Bug) AND project in (Test,wrong_name) AND priority in (Highest)",
        "type in ('Bug') AND priority in ('Highest') AND project in ('Test','wrong_name')",
    ],
)
@pytest.mark.integration
@pytest.mark.skipif(
    not JIRA_USERNAME, reason="No Jira username set, run export JIRA_USERNAME=username"
)
@pytest.mark.skipif(
    not JIRA_TOKEN, reason="No Jira token set, run export JIRA_TOKEN=token"
)
def test_jira_search_with_jql(jql):
    collector = setup_jira_collector(
        JIRA_USERNAME,
        JIRA_TOKEN,
        jql_query_string=jql,
    )

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 103


@pytest.mark.parametrize(
    "jql",
    [
        'project in ("wrong_name") AND type in ("Bug") AND priority in ("Highest")',
        "type in (Bug) AND project in (wrong_name) AND priority in (Highest)",
        "type in ('Bug') AND priority in ('Highest') AND project in ('wrong_name')",
    ],
)
@pytest.mark.integration
@pytest.mark.skipif(
    not JIRA_USERNAME, reason="No Jira username set, run export JIRA_USERNAME=username"
)
@pytest.mark.skipif(
    not JIRA_TOKEN, reason="No Jira token set, run export JIRA_TOKEN=token"
)
def test_jira_search_with_jql_without_results(jql):
    collector = setup_jira_collector(
        JIRA_USERNAME,
        JIRA_TOKEN,
        jql_query_string=jql,
    )

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 0


@pytest.mark.integration
@pytest.mark.skipif(
    not JIRA_USERNAME, reason="No Jira username set, run export JIRA_USERNAME=username"
)
@pytest.mark.skipif(
    not JIRA_TOKEN, reason="No Jira token set, run export JIRA_TOKEN=token"
)
def test_jira_search_with_wrong_jql():
    collector = setup_jira_collector(
        JIRA_USERNAME,
        JIRA_TOKEN,
        jql_query_string='type in ("Not a type")',
    )

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 0


def test_jira_prometheus_register(monkeypatch: pytest.MonkeyPatch):
    def mock_search_issues(self):
        return []

    monkeypatch.setattr(JiraFailureCollector, "search_issues", mock_search_issues)
    collector = setup_jira_collector()

    REGISTRY.register(collector)  # type: ignore


def test_jira_exception_is_not_raised(monkeypatch: pytest.MonkeyPatch):
    def mock_jql_query_issues(self, jira_client, query_string):
        raise JIRAError(status_code=400, text="Fake search error")

    monkeypatch.setattr(JiraFailureCollector, "_connect_to_jira", lambda self: None)
    monkeypatch.setattr(
        JiraFailureCollector, "_jql_query_issues", mock_jql_query_issues
    )
    collector = setup_jira_collector()

    with nullcontext() as context:
        collector.search_issues()

    assert context is None


@pytest.mark.parametrize("projects", [PROJECTS_COMMA, PROJECTS_SPACES])
def test_jira_removes_duplicated_projects(projects: str):
    collector = setup_jira_collector(projects=projects)

    assert collector.projects == PROJECTS_UNIQUE


# Github Issue failure exporter tests


def setup_github_collector(
    monkeypatch: Optional[pytest.MonkeyPatch] = None,
) -> GithubFailureCollector:
    if monkeypatch:

        def _no_github_user(self):
            return None

        monkeypatch.setattr(GithubFailureCollector, "_get_github_user", _no_github_user)

    return GithubFailureCollector(token="WIEds4uZHiCGnrtmgQPn9E7D")


def get_test_data(file="/exporters/tests/data/github_issue.json"):
    this_dir = os.path.dirname(os.path.abspath(__name__))
    test_file = this_dir + file
    with open(test_file) as json_file:
        data = json.load(json_file)
    return data


@pytest.mark.integration
def test_github_connection():
    with pytest.raises(GithubAuthenticationError) as context_ex:
        setup_github_collector()
    assert "Check the TOKEN: not authorized, invalid credentials" in str(
        context_ex.value
    )


def test_github_prometheus_register(monkeypatch: pytest.MonkeyPatch):
    def mock_search_issues(self):
        return []

    monkeypatch.setattr(GithubFailureCollector, "search_issues", mock_search_issues)
    collector = setup_github_collector(monkeypatch)
    REGISTRY.register(collector)  # type: ignore


# has label bug and app_label
def test_github_search_issues(monkeypatch: pytest.MonkeyPatch):
    def mock_get_issues(self):
        data = get_test_data()
        issue = data["good_example"]
        return [issue]

    monkeypatch.setattr(GithubFailureCollector, "get_issues", mock_get_issues)
    collector = setup_github_collector(monkeypatch)
    critical_issues = collector.search_issues()
    assert critical_issues[0].app == "todolist"
    assert critical_issues[0].issue_number == "3"
    assert critical_issues[0].creationdate == float(1652305808.0)
    assert critical_issues[0].resolutiondate is None


# has label fug ( not bug ) and app_label
def test_negative_github_search_issues(monkeypatch: pytest.MonkeyPatch):
    def mock_get_issues(self):
        data = get_test_data()
        issue = data["no_bug"]
        return [issue]

    monkeypatch.setattr(GithubFailureCollector, "get_issues", mock_get_issues)
    collector = setup_github_collector(monkeypatch)
    critical_issues = collector.search_issues()
    assert critical_issues == []


# has label bug and NOT app_label
def test_negative_label_github_search_issues(monkeypatch: pytest.MonkeyPatch):
    def mock_get_issues(self):
        data = get_test_data()
        issue = data["no_label"]
        return [issue]

    monkeypatch.setattr(GithubFailureCollector, "get_issues", mock_get_issues)
    collector = setup_github_collector(monkeypatch)
    critical_issues = collector.search_issues()
    assert critical_issues == []


# closed bug w/ proper labels
def test_github_closed_issue_search_issues(monkeypatch: pytest.MonkeyPatch):
    def mock_get_issues(self):
        data = get_test_data()
        issue = data["closed_example"]
        return [issue]

    monkeypatch.setattr(GithubFailureCollector, "get_issues", mock_get_issues)
    collector = setup_github_collector(monkeypatch)
    critical_issues = collector.search_issues()
    assert critical_issues[0].app == "todolist"
    assert critical_issues[0].issue_number == "3"
    assert critical_issues[0].creationdate == float(1652305808.0)
    assert critical_issues[0].resolutiondate == float(1653672080.0)


def test_default_jql_search_query():
    env = {collector_jira.JQL_SEARCH_QUERY_ENV: collector_jira.DEFAULT_JQL_SEARCH_QUERY}
    projects = {"custom", "projects"}

    collector = load_and_log(
        JiraFailureCollector,
        env=env,
        other=dict(
            tracker_api=JIRA_SERVER,
            projects=projects,
        ),
    )
    assert collector_jira.DEFAULT_JQL_SEARCH_QUERY in collector.jql_query_string

    assert collector.query_result_fields_string == collector_jira.QUERY_RESULT_FIELDS

    assert "AND project in (" in collector.jql_query_string
    assert '"custom"' in collector.jql_query_string
    assert '"projects"' in collector.jql_query_string

    for project in projects:
        assert f'"{project}"' in collector.jql_query_string


def test_custom_jql_search_query():
    custom_jql_query = "custom JIRA JQL query"
    env = {collector_jira.JQL_SEARCH_QUERY_ENV: custom_jql_query}

    collector = load_and_log(
        JiraFailureCollector,
        env=env,
        other=dict(
            tracker_api=JIRA_SERVER,
            projects={"custom", "projects"},
        ),
    )
    assert collector.jql_query_string == custom_jql_query

    assert collector.query_result_fields_string == ""

    assert "AND project" not in collector.jql_query_string


def test_no_resolved_timestamp():
    collector = setup_jira_collector()

    issue_fields = {
        "key": "EXAMPLE-1",
        "fields": {
            "summary": "Example issue with no resolutiondate and no custom field",
            "resolutiondate": None,
        },
    }
    test_issue = Issue(None, None, issue_fields)  # type: ignore
    resolution_timestamp = collector._get_resolved_timestamp(test_issue)

    assert resolution_timestamp is None


def test_custom_resolved_timestamp():
    collector = setup_jira_collector()

    issue_fields = {
        "key": "EXAMPLE-1",
        "fields": {
            "summary": "Example issue to present custom field to calculate resolved timestamp with no resolutiondate",
            "statuscategorychangedate": "2022-05-13T00:50:43.471+0200",
            "resolutiondate": None,
            "status": {
                "name": "Done",
            },
        },
    }
    test_issue = Issue(None, None, issue_fields)  # type: ignore

    resolution_timestamp = collector._get_resolved_timestamp(
        test_issue, "Done, Resolved, Other"
    )

    assert int(resolution_timestamp) == 1652395843  # type: ignore


def test_resolutiondate_timestamp():
    collector = setup_jira_collector()

    issue_fields = {
        "key": "EXAMPLE-1",
        "fields": {
            "summary": "Example issue to use resolutionfield to calculate resolved timestamp",
            "resolutiondate": "2022-04-13T00:50:43.471+0200",
            "status": {},
        },
    }
    test_issue = Issue(None, None, issue_fields)  # type: ignore

    resolution_timestamp = collector._get_resolved_timestamp(test_issue)

    assert int(resolution_timestamp) == 1649803843  # type: ignore

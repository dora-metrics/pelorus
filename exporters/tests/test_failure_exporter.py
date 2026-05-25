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
from pathlib import Path
from typing import Optional
from unittest import mock

import pytest
from jira.exceptions import JIRAError
from jira.resources import Issue

from failure import collector_jira
from failure.collector_github import GitHubFailureCollector
from failure.collector_jira import DEFAULT_JQL_SEARCH_QUERY, JiraFailureCollector
from pelorus.config import load_and_log
from failure.collector_base import FailureProviderAuthenticationError
from tests import run_prometheus_register

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
    app_name: Optional[str] = None,
) -> JiraFailureCollector:
    return JiraFailureCollector(
        tracker_api=JIRA_SERVER,
        username=username,
        token=token,
        projects=projects,
        jql_query_string=jql_query_string,
        app_name=app_name,
    )


@pytest.mark.parametrize("token", ["WIEds4uZHiCGnrtmgQPn9E7D", "fakepass"])
@pytest.mark.integration
def test_jira_error_connection(token: str):
    collector = setup_jira_collector(token=token)
    with pytest.raises(JIRAError):
        collector._connect_to_jira()


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

    issues = collector.search_issues()

    assert len(issues) == 103
    assert len([issue for issue in issues if issue.app == "unknown"]) == 4


@pytest.mark.integration
@pytest.mark.skipif(
    not JIRA_USERNAME, reason="No Jira username set, run export JIRA_USERNAME=username"
)
@pytest.mark.skipif(
    not JIRA_TOKEN, reason="No Jira token set, run export JIRA_TOKEN=token"
)
def test_jira_search_with_app_name():
    collector = setup_jira_collector(
        JIRA_USERNAME, JIRA_TOKEN, projects="Test", app_name="robotron"
    )

    issues = collector.search_issues()

    assert len(issues) == 103
    assert len([issue for issue in issues if issue.app == "unknown"]) == 0
    assert len([issue for issue in issues if issue.app == "robotron"]) == 4


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

    issues = collector.search_issues()

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

    issues = collector.search_issues()

    assert len(issues) == 103
    assert len([issue for issue in issues if issue.app == "unknown"]) == 4


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

    issues = collector.search_issues()

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

    issues = collector.search_issues()

    assert len(issues) == 0


@mock.patch("failure.collector_jira.set_up_requests_certs")
@mock.patch("failure.collector_jira.JIRA")
def test_basic_auth_connect_to_jira(jira_mock, certs_mock):
    jira_client_mock = mock.MagicMock()
    jira_mock.return_value = jira_client_mock
    certs_mock.return_value = "/path/to/certs.pem"

    collector = JiraFailureCollector(
        tracker_api="https://my.jira.server.com", username="user", token="token"
    )
    jira_client = collector._connect_to_jira()
    jira_client_mock.session.assert_called_once()

    jira_mock.assert_called_once_with(
        options={"server": "https://my.jira.server.com", "verify": "/path/to/certs.pem"},
        basic_auth=("user", "token"),
    )
    assert jira_client == jira_client_mock


@mock.patch("failure.collector_jira.set_up_requests_certs")
@mock.patch("failure.collector_jira.JIRA")
def test_token_auth_connect_to_jira(jira_mock, certs_mock):
    jira_client_mock = mock.MagicMock()
    jira_mock.return_value = jira_client_mock
    certs_mock.return_value = "/path/to/certs.pem"

    collector = JiraFailureCollector(
        tracker_api="https://my.jira.server.com", token="token"
    )
    jira_client = collector._connect_to_jira()
    jira_client_mock.session.assert_called_once()

    jira_mock.assert_called_once_with(
        options={"server": "https://my.jira.server.com", "verify": "/path/to/certs.pem"},
        token_auth="token",
    )
    assert jira_client == jira_client_mock


def test_jira_prometheus_register(monkeypatch: pytest.MonkeyPatch):
    def mock_search_issues(self):
        return []

    monkeypatch.setattr(JiraFailureCollector, "search_issues", mock_search_issues)
    collector = setup_jira_collector()

    run_prometheus_register(collector)


def test_jira_exception_is_not_raised(monkeypatch: pytest.MonkeyPatch):
    def mock_jql_query_issues(self, jira_client, query_string):
        raise JIRAError(status_code=400, text="Fake search error")

    monkeypatch.setattr(JiraFailureCollector, "_connect_to_jira", lambda self: None)
    monkeypatch.setattr(
        JiraFailureCollector, "_jql_query_issues", mock_jql_query_issues
    )
    collector = setup_jira_collector()

    issues = collector.search_issues()
    assert issues == []


@pytest.mark.parametrize("projects", [PROJECTS_COMMA, PROJECTS_SPACES])
def test_jira_removes_duplicated_projects(projects: str):
    collector = setup_jira_collector(projects=projects)

    assert collector.projects == PROJECTS_UNIQUE


# Github Issue failure exporter tests


def setup_github_collector(
    monkeypatch: Optional[pytest.MonkeyPatch] = None,
) -> GitHubFailureCollector:
    if monkeypatch:

        def _no_github_user(self):
            return None

        monkeypatch.setattr(GitHubFailureCollector, "_get_github_user", _no_github_user)

    return GitHubFailureCollector(token="test-token-not-real")


def get_test_data(filename="github_issue.json"):
    test_file = Path(__file__).resolve().parent / "data" / filename
    with open(test_file) as json_file:
        data = json.load(json_file)
    return data


@pytest.mark.integration
def test_github_connection():
    with pytest.raises(FailureProviderAuthenticationError) as context_ex:
        setup_github_collector()
    assert "Check the TOKEN: not authorized, invalid credentials" in str(
        context_ex.value
    )


def test_github_prometheus_register(monkeypatch: pytest.MonkeyPatch):
    def mock_search_issues(self):
        return []

    monkeypatch.setattr(GitHubFailureCollector, "search_issues", mock_search_issues)
    collector = setup_github_collector(monkeypatch)

    run_prometheus_register(collector)


def test_github_search_issues(monkeypatch: pytest.MonkeyPatch):
    def mock_get_issues(self):
        data = get_test_data()
        issue = data["good_example"]
        return [issue]

    monkeypatch.setattr(GitHubFailureCollector, "get_issues", mock_get_issues)
    collector = setup_github_collector(monkeypatch)
    critical_issues = collector.search_issues()
    assert critical_issues[0].app == "todolist"
    assert critical_issues[0].issue_number == "3"
    assert critical_issues[0].creationdate == float(1652305808.0)
    assert critical_issues[0].resolutiondate is None


def test_negative_github_search_issues(monkeypatch: pytest.MonkeyPatch):
    def mock_get_issues(self):
        data = get_test_data()
        issue = data["no_bug"]
        return [issue]

    monkeypatch.setattr(GitHubFailureCollector, "get_issues", mock_get_issues)
    collector = setup_github_collector(monkeypatch)
    critical_issues = collector.search_issues()
    assert critical_issues == []


def test_negative_label_github_search_issues(monkeypatch: pytest.MonkeyPatch):
    def mock_get_issues(self):
        data = get_test_data()
        issue = data["no_label"]
        return [issue]

    monkeypatch.setattr(GitHubFailureCollector, "get_issues", mock_get_issues)
    collector = setup_github_collector(monkeypatch)
    critical_issues = collector.search_issues()
    assert critical_issues == []


def test_github_closed_issue_search_issues(monkeypatch: pytest.MonkeyPatch):
    def mock_get_issues(self):
        data = get_test_data()
        issue = data["closed_example"]
        return [issue]

    monkeypatch.setattr(GitHubFailureCollector, "get_issues", mock_get_issues)
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
    collector.jira_resolved_statuses = "Done, Resolved, Other"
    collector._resolved_statuses_list = ["done", "resolved", "other"]

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

    resolution_timestamp = collector._get_resolved_timestamp(test_issue)

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

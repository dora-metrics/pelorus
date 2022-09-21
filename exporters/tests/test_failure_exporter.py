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
from typing import Optional
from unittest import mock  # NOQA

import pytest
from jira.exceptions import JIRAError
from jira.resources import Issue
from prometheus_client.core import REGISTRY

from failure import collector_jira
from failure.collector_github import GithubAuthenticationError, GithubFailureCollector
from failure.collector_jira import JiraFailureCollector


def setup_jira_collector(server, username, apikey) -> JiraFailureCollector:
    return JiraFailureCollector(
        server=server,
        user=username,
        apikey=apikey,
        projects=None,
    )


@pytest.mark.parametrize(
    "server, username, apikey",
    [
        (
            "https://pelorustest.atlassian.net",
            "fake@user.com",
            "WIEds4uZHiCGnrtmgQPn9E7D",
        )
    ],
)
@pytest.mark.integration
def test_jira_connection(server, username, apikey):
    collector = setup_jira_collector(server, username, apikey)
    with pytest.raises(JIRAError) as context_ex:
        collector._connect_to_jira()
    assert (
        "You are not authenticated. Authentication required to perform this operation."
        in str(context_ex.value)
    )


@pytest.mark.parametrize(
    "server, username, apikey",
    [("https://pelorustest.atlassian.net", "fake@user.com", "fakepass")],
)
@pytest.mark.integration
def test_jira_pass_connection(server, username, apikey):
    collector = setup_jira_collector(server, username, apikey)
    with pytest.raises(JIRAError) as context_ex:
        collector._connect_to_jira()
    assert "Basic authentication with passwords is deprecated" in str(context_ex.value)


@pytest.mark.parametrize(
    "server, username, apikey",
    [
        (
            "https://pelorustest.atlassian.net",
            "fake@user.com",
            "WIEds4uZHiCGnrtmgQPn9E7D",
        )
    ],
)
def test_jira_prometheus_register(
    server, username, apikey, monkeypatch: pytest.MonkeyPatch
):
    def mock_search_issues(self):
        return []

    monkeypatch.setattr(JiraFailureCollector, "search_issues", mock_search_issues)
    collector = JiraFailureCollector(
        user=username,
        apikey=apikey,
        server=server,
        projects=None,
    )

    REGISTRY.register(collector)  # type: ignore


@pytest.mark.parametrize(
    "server, username, apikey",
    [
        (
            "https://pelorustest.atlassian.net",
            "fake@user.com",
            "WIEds4uZHiCGnrtmgQPn9E7D",
        )
    ],
)
def test_jira_exception(server, username, apikey, monkeypatch: pytest.MonkeyPatch):
    class FakeJira(object):
        def search_issues(self, issues, startAt=0, maxResults=50, fields=None):
            raise JIRAError(status_code=400, text="Fake search error")

    def mock_jira_connect(self):
        return FakeJira()

    monkeypatch.setattr(JiraFailureCollector, "_connect_to_jira", mock_jira_connect)

    collector = JiraFailureCollector(
        user=username,
        apikey=apikey,
        server=server,
        projects=None,
    )
    collector.search_issues()


# Github Issue failure exporter tests


def setup_github_collector(
    monkeypatch: Optional[pytest.MonkeyPatch] = None,
) -> GithubFailureCollector:
    if monkeypatch:

        def _no_github_user(self):
            return None

        monkeypatch.setattr(GithubFailureCollector, "_get_github_user", _no_github_user)

    return GithubFailureCollector("WIEds4uZHiCGnrtmgQPn9E7D", None)


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


# has label bug and pelorus.get_app_label()
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


# has label fug ( not bug ) and pelorus.get_app_label()
def test_negative_github_search_issues(monkeypatch: pytest.MonkeyPatch):
    def mock_get_issues(self):
        data = get_test_data()
        issue = data["no_bug"]
        return [issue]

    monkeypatch.setattr(GithubFailureCollector, "get_issues", mock_get_issues)
    collector = setup_github_collector(monkeypatch)
    critical_issues = collector.search_issues()
    assert critical_issues == []


# has label bug and NOT pelorus.get_app_label()
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


@pytest.mark.parametrize(
    "server, username, apikey",
    [
        (
            "https://pelorustest.atlassian.net",
            "fake@user.com",
            "WIEds4uZHiCGnrtmgQPn9E7D",
        )
    ],
)
def test_default_jql_search_query(server, username, apikey):
    os.environ[
        collector_jira.JQL_SEARCH_QUERY_ENV
    ] = collector_jira.DEFAULT_JQL_SEARCH_QUERY

    collector = JiraFailureCollector(
        user=username,
        apikey=apikey,
        server=server,
        projects="custom,projects",
    )
    assert collector_jira.DEFAULT_JQL_SEARCH_QUERY in collector.jql_query_string

    assert collector.query_result_fields_string == collector_jira.QUERY_RESULT_FIELDS

    assert 'AND project in ("custom","projects")' in collector.jql_query_string

    del os.environ[collector_jira.JQL_SEARCH_QUERY_ENV]


@pytest.mark.parametrize(
    "server, username, apikey",
    [
        (
            "https://pelorustest.atlassian.net",
            "fake@user.com",
            "WIEds4uZHiCGnrtmgQPn9E7D",
        )
    ],
)
def test_custom_jql_search_query(server, username, apikey):

    custom_jql_query = "custom JIRA JQL query"

    os.environ[collector_jira.JQL_SEARCH_QUERY_ENV] = custom_jql_query

    collector = JiraFailureCollector(
        user=username,
        apikey=apikey,
        server=server,
        projects="custom,projects",
    )
    assert collector.jql_query_string == custom_jql_query

    assert collector.query_result_fields_string == ""

    assert "AND project" not in collector.jql_query_string

    del os.environ[collector_jira.JQL_SEARCH_QUERY_ENV]


@pytest.mark.parametrize(
    "server, username, apikey",
    [
        (
            "https://pelorustest.atlassian.net",
            "fake@user.com",
            "WIEds4uZHiCGnrtmgQPn9E7D",
        )
    ],
)
def test_no_resolved_timestamp(server, username, apikey):

    collector = JiraFailureCollector(
        user=username,
        apikey=apikey,
        server=server,
        projects=None,
    )

    issue_fields = {
        "key": "EXAMPLE-1",
        "fields": {
            "summary": "Example issue with no resolutiondate and no custom field",
            "resolutiondate": None,
        },
    }
    test_issue = Issue(None, None, issue_fields)
    resolution_timestamp = collector._get_resolved_timestamp(test_issue)

    assert resolution_timestamp is None


@pytest.mark.parametrize(
    "server, username, apikey",
    [
        (
            "https://pelorustest.atlassian.net",
            "fake@user.com",
            "WIEds4uZHiCGnrtmgQPn9E7D",
        )
    ],
)
def test_custom_resolved_timestamp(server, username, apikey):

    collector = JiraFailureCollector(
        user=username,
        apikey=apikey,
        server=server,
        projects=None,
    )

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
    test_issue = Issue(None, None, issue_fields)

    resolution_timestamp = collector._get_resolved_timestamp(
        test_issue, "Done, Resolved, Other"
    )

    assert int(resolution_timestamp) == 1652395843


@pytest.mark.parametrize(
    "server, username, apikey",
    [
        (
            "https://pelorustest.atlassian.net",
            "fake@user.com",
            "WIEds4uZHiCGnrtmgQPn9E7D",
        )
    ],
)
def test_resolutiondate_timestamp(server, username, apikey):

    collector = JiraFailureCollector(
        user=username,
        apikey=apikey,
        server=server,
        projects=None,
    )

    issue_fields = {
        "key": "EXAMPLE-1",
        "fields": {
            "summary": "Example issue to use resolutionfield to calculate resolved timestamp",
            "resolutiondate": "2022-04-13T00:50:43.471+0200",
            "status": {},
        },
    }
    test_issue = Issue(None, None, issue_fields)

    resolution_timestamp = collector._get_resolved_timestamp(test_issue)

    assert int(resolution_timestamp) == 1649803843

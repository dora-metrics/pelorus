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

from typing import cast

import pytest
from jira.exceptions import JIRAError
from prometheus_client.core import REGISTRY

from failure.app import TrackerFactory
from failure.collector_jira import JiraFailureCollector


def setup_jira_collector(server, username, apikey) -> JiraFailureCollector:
    tracker_provider = "jira"
    projects = None
    jira_collector = TrackerFactory.getCollector(
        username, apikey, server, projects, tracker_provider
    )
    return cast(JiraFailureCollector, jira_collector)


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
        user=username, apikey=apikey, server=server, projects=None
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
        user=username, apikey=apikey, server=server, projects=None
    )
    collector.search_issues()

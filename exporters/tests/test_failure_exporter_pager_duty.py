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

import os
from contextlib import nullcontext
from typing import Optional

import pytest

from failure.collector_pagerduty import PagerdutyFailureCollector
from tests import run_prometheus_register

PAGER_DUTY_TOKEN = os.environ.get("PAGER_DUTY_TOKEN")
NUMBER_OF_INCIDENTS = {
    "null": 41,
    "P1": 16,
    "P2": 0,
    "P3": 0,
    "P4": 0,
    "P5": 0,
    "high": 46,
    "low": 11,
}


def setup_pager_duty_collector(
    token: str = "fake_token",
    incident_urgency: Optional[str] = None,
    incident_priority: Optional[str] = None,
) -> PagerdutyFailureCollector:
    return PagerdutyFailureCollector(
        token=token,
        incident_urgency=incident_urgency,
        incident_priority=incident_priority,
    )


@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_pager_duty_search():
    collector = setup_pager_duty_collector(PAGER_DUTY_TOKEN)

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 57
    assert len([issue for issue in issues if issue.resolutiondate is None]) == 52
    assert len([issue for issue in issues if issue.resolutiondate]) == 5


@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_pager_duty_search_with_multiple_filters():
    collector = setup_pager_duty_collector(
        PAGER_DUTY_TOKEN, incident_urgency="low,high", incident_priority="P1,P3"
    )

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 16


@pytest.mark.parametrize("priority", ["null", "P1", "P2", "P3", "P4", "P5"])
@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_pager_duty_search_with_priority(priority: str):
    collector = setup_pager_duty_collector(PAGER_DUTY_TOKEN, incident_priority=priority)

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == NUMBER_OF_INCIDENTS[priority]


@pytest.mark.parametrize("priority", ["wrong", "not_available"])
@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_pager_duty_search_with_wrong_priority(priority: str):
    collector = setup_pager_duty_collector(PAGER_DUTY_TOKEN, incident_priority=priority)

    with nullcontext() as context:
        # TODO should break or at least warn user?
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 0


@pytest.mark.parametrize("urgency", ["low", "high"])
@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_pager_duty_search_with_urgency(urgency: str):
    collector = setup_pager_duty_collector(PAGER_DUTY_TOKEN, incident_urgency=urgency)

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == NUMBER_OF_INCIDENTS[urgency]


@pytest.mark.parametrize("urgency", ["wrong", "not_available"])
@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_pager_duty_search_with_wrong_urgency(urgency: str):
    collector = setup_pager_duty_collector(PAGER_DUTY_TOKEN, incident_urgency=urgency)

    with nullcontext() as context:
        # TODO should break or at least warn user?
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 0


def test_pager_duty_prometheus_register(monkeypatch: pytest.MonkeyPatch):
    def mock_search_issues(self):
        return []

    monkeypatch.setattr(PagerdutyFailureCollector, "search_issues", mock_search_issues)
    collector = setup_pager_duty_collector()

    with nullcontext() as context:
        run_prometheus_register(collector)

    assert context is None

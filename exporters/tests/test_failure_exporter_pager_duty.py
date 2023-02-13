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

import os
from contextlib import nullcontext
from typing import Optional

import pytest
from prometheus_client.core import REGISTRY

from failure.collector_pagerduty import PagerdutyFailureCollector
from pelorus.errors import FailureProviderAuthenticationError

PAGER_DUTY_TOKEN = os.environ.get("PAGER_DUTY_TOKEN")


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
def test_pager_duty_connection():
    collector = setup_pager_duty_collector()
    with pytest.raises(FailureProviderAuthenticationError) as auth_error:
        collector.search_issues()
    assert "Check the TOKEN: not authorized, invalid credentials" in str(
        auth_error.value
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
    assert len(issues) == 7
    assert len([issue for issue in issues if issue.resolutiondate is None]) == 2


@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_pager_duty_search_with_multiple_filters():
    collector = setup_pager_duty_collector(
        PAGER_DUTY_TOKEN, incident_urgency="low,high", incident_priority="null,P3"
    )

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 6


@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_pager_duty_search_with_priority_null():
    collector = setup_pager_duty_collector(PAGER_DUTY_TOKEN, incident_priority="null")

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 6


@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_pager_duty_search_with_priority_p1():
    collector = setup_pager_duty_collector(PAGER_DUTY_TOKEN, incident_priority="P1")

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 1


@pytest.mark.parametrize("priority", ["P2", "P3", "P4", "P5"])
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
    assert len(issues) == 0


@pytest.mark.parametrize("priority", ["wrong", "not_available"])
@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_pager_duty_search_with_wrong_priority(priority: str):
    collector = setup_pager_duty_collector(PAGER_DUTY_TOKEN, incident_priority=priority)

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 0


@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_pager_duty_search_with_urgency_low():
    collector = setup_pager_duty_collector(PAGER_DUTY_TOKEN, incident_urgency="low")

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 1


@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_pager_duty_search_with_urgency_high():
    collector = setup_pager_duty_collector(PAGER_DUTY_TOKEN, incident_urgency="high")

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 6


@pytest.mark.parametrize("urgency", ["wrong", "not_available"])
@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_pager_duty_search_with_wrong_urgency(urgency: str):
    collector = setup_pager_duty_collector(PAGER_DUTY_TOKEN, incident_urgency=urgency)

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 0


def test_pager_duty_prometheus_register(monkeypatch: pytest.MonkeyPatch):
    def mock_search_issues(self):
        return []

    monkeypatch.setattr(PagerdutyFailureCollector, "search_issues", mock_search_issues)
    collector = setup_pager_duty_collector()

    REGISTRY.register(collector)

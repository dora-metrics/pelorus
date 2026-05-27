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

import pytest
from prometheus_client.core import Metric

from failure.app import set_up
from pelorus.config.loading import MissingConfigDataError
from failure.collector_base import FailureProviderAuthenticationError
from tests import MockExporter, get_number_of_error_logs, get_number_of_info_logs

PAGER_DUTY_TOKEN = os.environ.get("PAGER_DUTY_TOKEN")
AZURE_DEVOPS_TOKEN = os.environ.get("AZURE_DEVOPS_TOKEN")
JIRA_USERNAME = os.environ.get("JIRA_USERNAME")
JIRA_TOKEN = os.environ.get("JIRA_TOKEN")

@pytest.fixture
def mocked_failure_exporter():
    return MockExporter(set_up=set_up)


@pytest.mark.parametrize("provider", ["wrong", "git_hub", "GITHUB", "GitHub"])
@pytest.mark.integration
def test_app_invalid_provider(provider: str, caplog: pytest.LogCaptureFixture, mocked_failure_exporter):
    with pytest.raises(ValueError):
        mocked_failure_exporter.run_app({"PROVIDER": provider})

    assert get_number_of_error_logs(caplog.record_tuples) == 0


@pytest.mark.integration
def test_app_pagerduty_without_required_options(caplog: pytest.LogCaptureFixture, mocked_failure_exporter):
    collector = mocked_failure_exporter.run_app({"PROVIDER": "pagerduty"})
    metrics = list(collector.collect())
    assert len(metrics) == 2
    for m in metrics:
        assert isinstance(m, Metric)
    assert get_number_of_error_logs(caplog.record_tuples) >= 1


@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_app_pagerduty_with_required_options(caplog: pytest.LogCaptureFixture, mocked_failure_exporter):
    mocked_failure_exporter.run_app(
        {"PROVIDER": "pagerduty", "TOKEN": PAGER_DUTY_TOKEN}
    )

    captured_logs = caplog.record_tuples
    assert "Collected " not in caplog.text
    assert get_number_of_info_logs(captured_logs) >= 1
    assert get_number_of_error_logs(captured_logs) == 0


@pytest.mark.integration
def test_app_azure_devops_without_required_options(caplog: pytest.LogCaptureFixture, mocked_failure_exporter):
    with pytest.raises(MissingConfigDataError):
        mocked_failure_exporter.run_app({"PROVIDER": "azure-devops"})

    assert get_number_of_error_logs(caplog.record_tuples) >= 1


@pytest.mark.integration
def test_app_azure_devops_with_wrong_token(caplog: pytest.LogCaptureFixture, mocked_failure_exporter):
    with pytest.raises(FailureProviderAuthenticationError):
        mocked_failure_exporter.run_app(
            {
                "PROVIDER": "azure-devops",
                "TOKEN": "fake_token",
                "SERVER": "dev.azure.com/matews1943",
            }
        )

    assert get_number_of_error_logs(caplog.record_tuples) == 1


@pytest.mark.integration
@pytest.mark.skipif(
    not AZURE_DEVOPS_TOKEN,
    reason="No Azure DevOps token set, run export AZURE_DEVOPS_TOKEN=token",
)
def test_app_azure_devops_with_required_options(caplog: pytest.LogCaptureFixture, mocked_failure_exporter):
    mocked_failure_exporter.run_app(
        {
            "PROVIDER": "azure-devops",
            "TOKEN": AZURE_DEVOPS_TOKEN,
            "SERVER": "dev.azure.com/matews1943",
        }
    )

    captured_logs = caplog.record_tuples
    assert "Collected " not in caplog.text
    assert get_number_of_info_logs(captured_logs) >= 1
    assert get_number_of_error_logs(captured_logs) == 0


@pytest.mark.integration
def test_app_jira_without_required_options(caplog: pytest.LogCaptureFixture, mocked_failure_exporter):
    with pytest.raises(MissingConfigDataError):
        mocked_failure_exporter.run_app({"PROVIDER": "jira"})

    assert get_number_of_error_logs(caplog.record_tuples) >= 1


@pytest.mark.integration
def test_app_jira_with_wrong_token(caplog: pytest.LogCaptureFixture, mocked_failure_exporter):
    collector = mocked_failure_exporter.run_app(
        {
            "PROVIDER": "jira",
            "API_USER": "fake_user",
            "TOKEN": "fake_token",
            "SERVER": "https://pelorustest.atlassian.net",
        }
    )
    metrics = list(collector.collect())
    assert len(metrics) == 2
    for m in metrics:
        assert isinstance(m, Metric)
    assert get_number_of_error_logs(caplog.record_tuples) >= 1


@pytest.mark.integration
@pytest.mark.skipif(
    not JIRA_USERNAME, reason="No Jira username set, run export JIRA_USERNAME=username"
)
@pytest.mark.skipif(
    not JIRA_TOKEN, reason="No Jira token set, run export JIRA_TOKEN=token"
)
def test_app_jira_with_required_options(caplog: pytest.LogCaptureFixture, mocked_failure_exporter):
    mocked_failure_exporter.run_app(
        {
            "PROVIDER": "jira",
            "API_USER": JIRA_USERNAME,
            "TOKEN": JIRA_TOKEN,
            "SERVER": "https://pelorustest.atlassian.net",
        }
    )

    captured_logs = caplog.record_tuples
    assert "Collected " not in caplog.text
    assert get_number_of_info_logs(captured_logs) >= 1
    assert get_number_of_error_logs(captured_logs) == 0


@pytest.mark.integration
def test_app_github_without_required_options(caplog: pytest.LogCaptureFixture, mocked_failure_exporter):
    with pytest.raises(FailureProviderAuthenticationError):
        mocked_failure_exporter.run_app({"PROVIDER": "github"})

    assert get_number_of_error_logs(caplog.record_tuples) == 1


@pytest.mark.integration
def test_app_servicenow_without_required_options(caplog: pytest.LogCaptureFixture, mocked_failure_exporter):
    with pytest.raises(MissingConfigDataError):
        mocked_failure_exporter.run_app({"PROVIDER": "servicenow"})

    assert get_number_of_error_logs(caplog.record_tuples) >= 1

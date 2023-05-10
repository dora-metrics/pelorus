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

from failure.app import set_up
from pelorus.config.loading import MissingConfigDataError
from pelorus.errors import FailureProviderAuthenticationError
from tests import MockExporter

PAGER_DUTY_TOKEN = os.environ.get("PAGER_DUTY_TOKEN")
AZURE_DEVOPS_TOKEN = os.environ.get("AZURE_DEVOPS_TOKEN")

mocked_failure_exporter = MockExporter(set_up=set_up)


@pytest.mark.parametrize("provider", ["wrong", "git_hub", "GITHUB", "GitHub"])
@pytest.mark.integration
def test_app_invalid_provider(provider: str, caplog: pytest.LogCaptureFixture):
    with pytest.raises(ValueError):
        mocked_failure_exporter.run_app({"PROVIDER": provider})

    # TODO shouldn't be 1?
    # number of error logs
    assert len([record for record in caplog.record_tuples if record[1] == 40]) == 0


@pytest.mark.integration
def test_app_pagerduty_without_required_options(caplog: pytest.LogCaptureFixture):
    with pytest.raises(FailureProviderAuthenticationError):
        mocked_failure_exporter.run_app({"PROVIDER": "pagerduty"})

    # number of error logs
    assert len([record for record in caplog.record_tuples if record[1] == 40]) == 1


@pytest.mark.integration
@pytest.mark.skipif(
    not PAGER_DUTY_TOKEN,
    reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
)
def test_app_pagerduty_with_required_options(caplog: pytest.LogCaptureFixture):
    mocked_failure_exporter.run_app(
        {"PROVIDER": "pagerduty", "TOKEN": PAGER_DUTY_TOKEN}
    )

    captured_logs = caplog.record_tuples
    # 9 informational, 5 resolution, 58 creation
    assert len(captured_logs) == 72
    # number of error logs
    assert len([record for record in captured_logs if record[1] == 40]) == 0


@pytest.mark.integration
def test_app_azure_devops_without_required_options(caplog: pytest.LogCaptureFixture):
    with pytest.raises(MissingConfigDataError):
        mocked_failure_exporter.run_app({"PROVIDER": "azure-devops"})

    # number of error logs
    assert len([record for record in caplog.record_tuples if record[1] == 40]) == 7


@pytest.mark.integration
def test_app_azure_devops_with_wrong_token(caplog: pytest.LogCaptureFixture):
    with pytest.raises(FailureProviderAuthenticationError):
        mocked_failure_exporter.run_app(
            {
                "PROVIDER": "azure-devops",
                "TOKEN": "fake_token",
                "SERVER": "dev.azure.com/matews1943",
            }
        )

    # number of error logs
    assert len([record for record in caplog.record_tuples if record[1] == 40]) == 1


@pytest.mark.integration
@pytest.mark.skipif(
    not AZURE_DEVOPS_TOKEN,
    reason="No Azure DevOps token set, run export AZURE_DEVOPS_TOKEN=token",
)
def test_app_azure_devops_with_required_options(caplog: pytest.LogCaptureFixture):
    mocked_failure_exporter.run_app(
        {
            "PROVIDER": "azure-devops",
            "TOKEN": AZURE_DEVOPS_TOKEN,
            "SERVER": "dev.azure.com/matews1943",
        }
    )

    captured_logs = caplog.record_tuples
    # 10 informational, 3 resolution, 213 creation
    assert len(captured_logs) == 226
    # number of error logs
    assert len([record for record in captured_logs if record[1] == 40]) == 0

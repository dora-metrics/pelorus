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

from failure.collector_azure_devops import AzureDevOpsFailureCollector

AZURE_DEVOPS_TOKEN = os.environ.get("AZURE_DEVOPS_TOKEN")
NUMBER_OF_WORK_ITEMS = {
    # priority
    "1": 0,
    "2": 212,
    "3": 1,
    "4": 0,
    # type
    "Epic": 3,
    "Issue": 207,
    "Task": 3,
    # project
    "todolist": 3,
    "test-pelorus": 210,
    # app_label
    "app.kubernetes.io/name": 1,
    "custom": 2,
}


def setup_azure_devops_collector(
    token: str = "fake_token",
    app_label: str = "app.kubernetes.io/name",
    projects: Optional[str] = None,
    work_item_type: Optional[str] = None,
    work_item_priority: Optional[str] = None,
) -> AzureDevOpsFailureCollector:
    return AzureDevOpsFailureCollector(
        token=token,
        app_label=app_label,
        projects=projects,
        work_item_type=work_item_type,
        work_item_priority=work_item_priority,
        tracker_api="dev.azure.com/matews1943",
    )


@pytest.mark.integration
@pytest.mark.skipif(
    not AZURE_DEVOPS_TOKEN,
    reason="No Azure DevOps token set, run export AZURE_DEVOPS_TOKEN=token",
)
def test_azure_devops_search():
    collector = setup_azure_devops_collector(AZURE_DEVOPS_TOKEN)

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 213
    assert len([issue for issue in issues if issue.resolutiondate is None]) == 210
    assert len([issue for issue in issues if issue.resolutiondate]) == 3


@pytest.mark.integration
@pytest.mark.skipif(
    not AZURE_DEVOPS_TOKEN,
    reason="No Azure DevOps token set, run export AZURE_DEVOPS_TOKEN=token",
)
def test_azure_devops_search_with_multiple_filters():
    collector = setup_azure_devops_collector(
        AZURE_DEVOPS_TOKEN,
        work_item_type="Issue,Task,wrong",
        work_item_priority="1,3,87",
        projects="todolist,test-pelorus,wrong",
    )

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 1


@pytest.mark.parametrize("_type", ["Epic", "Issue", "Task"])
@pytest.mark.integration
@pytest.mark.skipif(
    not AZURE_DEVOPS_TOKEN,
    reason="No Azure DevOps token set, run export AZURE_DEVOPS_TOKEN=token",
)
def test_azure_devops_search_with_type(_type: str):
    collector = setup_azure_devops_collector(AZURE_DEVOPS_TOKEN, work_item_type=_type)

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == NUMBER_OF_WORK_ITEMS[_type]


@pytest.mark.parametrize("_type", ["wrong", "not_available"])
@pytest.mark.integration
@pytest.mark.skipif(
    not AZURE_DEVOPS_TOKEN,
    reason="No Azure DevOps token set, run export AZURE_DEVOPS_TOKEN=token",
)
def test_azure_devops_search_with_wrong_type(_type: str):
    collector = setup_azure_devops_collector(AZURE_DEVOPS_TOKEN, work_item_type=_type)

    with nullcontext() as context:
        # TODO should break or at least warn user?
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 0


@pytest.mark.parametrize("priority", ["1", "2", "3", "4"])
@pytest.mark.integration
@pytest.mark.skipif(
    not AZURE_DEVOPS_TOKEN,
    reason="No Azure DevOps token set, run export AZURE_DEVOPS_TOKEN=token",
)
def test_azure_devops_search_with_priority(priority: str):
    collector = setup_azure_devops_collector(
        AZURE_DEVOPS_TOKEN, work_item_priority=priority
    )

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == NUMBER_OF_WORK_ITEMS[priority]


@pytest.mark.parametrize("priority", ["5", "6"])
@pytest.mark.integration
@pytest.mark.skipif(
    not AZURE_DEVOPS_TOKEN,
    reason="No Azure DevOps token set, run export AZURE_DEVOPS_TOKEN=token",
)
def test_azure_devops_search_with_wrong_priority(priority: str):
    collector = setup_azure_devops_collector(
        AZURE_DEVOPS_TOKEN, work_item_priority=priority
    )

    with nullcontext() as context:
        # TODO should break or at least warn user?
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 0


@pytest.mark.parametrize("project", ["todolist", "test-pelorus"])
@pytest.mark.integration
@pytest.mark.skipif(
    not AZURE_DEVOPS_TOKEN,
    reason="No Azure DevOps token set, run export AZURE_DEVOPS_TOKEN=token",
)
def test_azure_devops_search_with_project(project: str):
    collector = setup_azure_devops_collector(AZURE_DEVOPS_TOKEN, projects=project)

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == NUMBER_OF_WORK_ITEMS[project]


@pytest.mark.parametrize("project", ["wrong", "not_available"])
@pytest.mark.integration
@pytest.mark.skipif(
    not AZURE_DEVOPS_TOKEN,
    reason="No Azure DevOps token set, run export AZURE_DEVOPS_TOKEN=token",
)
def test_azure_devops_search_with_wrong_project(project: str):
    collector = setup_azure_devops_collector(AZURE_DEVOPS_TOKEN, projects=project)

    with nullcontext() as context:
        # TODO should break or at least warn user?
        issues = collector.search_issues()

    assert context is None
    assert len(issues) == 0


@pytest.mark.parametrize("app_label", ["app.kubernetes.io/name", "custom"])
@pytest.mark.integration
@pytest.mark.skipif(
    not AZURE_DEVOPS_TOKEN,
    reason="No Azure DevOps token set, run export AZURE_DEVOPS_TOKEN=token",
)
def test_azure_devops_search_with_app_label(app_label: str):
    collector = setup_azure_devops_collector(AZURE_DEVOPS_TOKEN, app_label=app_label)

    with nullcontext() as context:
        issues = collector.search_issues()

    assert context is None
    assert (
        len([issue for issue in issues if issue.app != "unknown"])
        == NUMBER_OF_WORK_ITEMS[app_label]
    )  # that has label


@pytest.mark.parametrize("app_label", ["wrong", "not_available"])
@pytest.mark.integration
@pytest.mark.skipif(
    not AZURE_DEVOPS_TOKEN,
    reason="No Azure DevOps token set, run export AZURE_DEVOPS_TOKEN=token",
)
def test_azure_devops_search_with_wrong_app_label(app_label: str):
    collector = setup_azure_devops_collector(AZURE_DEVOPS_TOKEN, app_label=app_label)

    with nullcontext() as context:
        # TODO should break or at least warn user?
        issues = collector.search_issues()

    assert context is None
    assert len([issue for issue in issues if issue.app != "unknown"]) == 0

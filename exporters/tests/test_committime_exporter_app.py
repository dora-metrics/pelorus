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

from unittest.mock import Mock

import pytest
from kubernetes.dynamic.resource import ResourceInstance

from committime.app import set_up
from committime.collector_azure_devops import AzureDevOpsCommitCollector
from tests import MockExporter


def name_space(name: str):
    namespace = Mock()
    namespace.metadata.name = name
    return namespace


namespaces = Mock()
namespaces.get.return_value.items = {name_space("test1"), name_space("test2")}
builds = Mock()
builds.get.return_value = {
    ResourceInstance(
        client=None,
        instance={"kind": "BuildList", "apiVersion": "build.openshift.io/v1"},
    )
}
images = Mock()
images.get.return_value = {
    ResourceInstance(
        client=None,
        instance={"kind": "ImageList", "apiVersion": "image.openshift.io/v1"},
    )
}


matcher = {
    "Namespace": namespaces,
    "Build": builds,
    "Image": images,
}


# TODO proper mock kubernetes objects
def mocked(api_version, kind):
    return matcher[kind]


mocked_commit_time_exporter = MockExporter(set_up=set_up, mock_kube_client=mocked)


@pytest.mark.parametrize("provider", ["imagy", "zip"])
@pytest.mark.integration
def test_app_invalid_provider(provider: str, caplog: pytest.LogCaptureFixture):
    with pytest.raises(ValueError):
        mocked_commit_time_exporter.run_app({"PROVIDER": provider})

    # TODO shouldn't be 1?
    # number of error logs
    assert len([record for record in caplog.record_tuples if record[1] == 40]) == 0


@pytest.mark.parametrize("provider", ["wrong", "git_hub", "GITHUB", "GitHub"])
@pytest.mark.integration
def test_app_git_invalid_git_provider(provider: str, caplog: pytest.LogCaptureFixture):
    with pytest.raises(ValueError):
        mocked_commit_time_exporter.run_app({"GIT_PROVIDER": provider})

    # TODO shouldn't be 1?
    # number of error logs
    assert len([record for record in caplog.record_tuples if record[1] == 40]) == 0


# TODO mock kubernetes/OpenShift objects so a call to azure API is made
# @pytest.mark.integration
# def test_app_git_azure_devops_without_required_options(caplog: pytest.LogCaptureFixture):
#     run_app({"GIT_PROVIDER": "azure-devops"})

#     # number of error logs
#     assert len([record for record in caplog.record_tuples if record[1] == 40]) == 1


@pytest.mark.integration
def test_app_git_azure_devops(caplog: pytest.LogCaptureFixture):
    mocked_exporter = mocked_commit_time_exporter.run_app(
        {
            "GIT_PROVIDER": "azure-devops",
            "API_USER": "fake_user",
            "TOKEN": "fake_token",
        }
    )

    assert "app_label='app.kubernetes.io/name'" in caplog.text
    assert mocked_exporter.app_label == "app.kubernetes.io/name"
    assert "hash_annotation_name='io.openshift.build.commit.id'" in caplog.text
    assert mocked_exporter.hash_annotation_name == "io.openshift.build.commit.id"
    assert (
        "repo_url_annotation_name='io.openshift.build.source-location'" in caplog.text
    )
    assert (
        mocked_exporter.repo_url_annotation_name == "io.openshift.build.source-location"
    )
    assert "provider='git'" in caplog.text
    assert "git_provider='azure-devops'" in caplog.text
    assert isinstance(mocked_exporter, AzureDevOpsCommitCollector)
    assert "username='fake_user'" in caplog.text
    assert mocked_exporter.username == "fake_user"
    assert "token=REDACTED, from env var TOKEN" in caplog.text
    assert mocked_exporter.token == "fake_token"
    # TODO assert "git_api='https://dev.azure.com'" in caplog.text
    assert mocked_exporter.git_api.url == "https://dev.azure.com"
    assert "No namespaces specified, watching all namespaces" in caplog.text
    assert len(mocked_exporter.namespaces) == 0
    # number of error logs
    assert len([record for record in caplog.record_tuples if record[1] == 40]) == 0


@pytest.mark.integration
def test_app_git_with_all_options(caplog: pytest.LogCaptureFixture):
    mocked_exporter = mocked_commit_time_exporter.run_app(
        {
            "LOG_LEVEL": "DEBUG",
            "APP_LABEL": "custom",
            # TODO how to test?
            "PELORUS_DEFAULT_KEYWORD": "another",
            "COMMIT_HASH_ANNOTATION": "annotation",
            "COMMIT_REPO_URL_ANNOTATION": "repo url",
            "PROVIDER": "git",
            "GIT_PROVIDER": "azure-devops",
            "NAMESPACES": "test1",
            "API_USER": "fake_user",
            "TOKEN": "fake_token",
            "GIT_API": "custom.io",
        }
    )

    assert "app_label='custom'" in caplog.text
    assert mocked_exporter.app_label == "custom"
    assert "hash_annotation_name='annotation'" in caplog.text
    assert mocked_exporter.hash_annotation_name == "annotation"
    assert "repo_url_annotation_name='repo url'" in caplog.text
    assert mocked_exporter.repo_url_annotation_name == "repo url"
    assert "provider='git'" in caplog.text
    assert "git_provider='azure-devops'" in caplog.text
    assert isinstance(mocked_exporter, AzureDevOpsCommitCollector)
    assert "username='fake_user'" in caplog.text
    assert mocked_exporter.username == "fake_user"
    assert "token=REDACTED, from env var TOKEN" in caplog.text
    assert mocked_exporter.token == "fake_token"
    assert "git_api='custom.io'" in caplog.text
    assert mocked_exporter.git_api.url == "https://custom.io"
    assert "Watching namespaces: {'test1'}" in caplog.text
    assert len(mocked_exporter.namespaces) == 1
    assert "test1" in mocked_exporter.namespaces
    # number of error logs
    assert len([record for record in caplog.record_tuples if record[1] == 40]) == 0


@pytest.mark.integration
def test_app_image(caplog: pytest.LogCaptureFixture):
    mocked_exporter = mocked_commit_time_exporter.run_app(
        {
            "PROVIDER": "image",
        }
    )

    assert "app_label='app.kubernetes.io/name'" in caplog.text
    assert mocked_exporter.app_label == "app.kubernetes.io/name"
    assert "provider='image'" in caplog.text
    assert "hash_annotation_name='io.openshift.build.commit.id'" in caplog.text
    assert mocked_exporter.hash_annotation_name == "io.openshift.build.commit.id"
    assert (
        "repo_url_annotation_name='io.openshift.build.source-location'" in caplog.text
    )
    assert (
        mocked_exporter.repo_url_annotation_name == "io.openshift.build.source-location"
    )
    assert "date_annotation_name='io.openshift.build.commit.date'" in caplog.text
    assert mocked_exporter.date_annotation_name == "io.openshift.build.commit.date"
    assert "date_format='%a %b %d %H:%M:%S %Y %z'" in caplog.text
    assert mocked_exporter.date_format == "%a %b %d %H:%M:%S %Y %z"
    # number of error logs
    assert len([record for record in caplog.record_tuples if record[1] == 40]) == 0


@pytest.mark.integration
def test_app_image_with_all_options(caplog: pytest.LogCaptureFixture):
    mocked_exporter = mocked_commit_time_exporter.run_app(
        {
            "LOG_LEVEL": "DEBUG",
            "PROVIDER": "image",
            "APP_LABEL": "another.one",
            # TODO how to test?
            "PELORUS_DEFAULT_KEYWORD": "another",
            "COMMIT_HASH_ANNOTATION": "custom annotation",
            "COMMIT_REPO_URL_ANNOTATION": "custom repo url",
            "COMMIT_DATE_ANNOTATION": "custom date annotation",
            "COMMIT_DATE_FORMAT": "custom format",
        }
    )

    assert "app_label='another.one'" in caplog.text
    assert mocked_exporter.app_label == "another.one"
    assert "provider='image'" in caplog.text
    assert "hash_annotation_name='custom annotation'" in caplog.text
    assert mocked_exporter.hash_annotation_name == "custom annotation"
    assert "repo_url_annotation_name='custom repo url'" in caplog.text
    assert mocked_exporter.repo_url_annotation_name == "custom repo url"
    assert "date_annotation_name='custom date annotation'" in caplog.text
    assert mocked_exporter.date_annotation_name == "custom date annotation"
    assert "date_format='custom format'" in caplog.text
    assert mocked_exporter.date_format == "custom format"
    # number of error logs
    assert len([record for record in caplog.record_tuples if record[1] == 40]) == 0

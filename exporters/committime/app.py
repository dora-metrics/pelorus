#!/usr/bin/python3
import time
from typing import Optional

import attrs.converters
import attrs.validators
from attrs import define, field
from kubernetes.dynamic import DynamicClient
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

import pelorus
from committime import CommitMetric
from committime.collector_azure_devops import AzureDevOpsCommitCollector
from committime.collector_base import (
    COMMIT_DATE_ANNOTATION_ENV,
    COMMIT_HASH_ANNOTATION_ENV,
    COMMIT_REPO_URL_ANNOTATION_ENV,
    AbstractCommitCollector,
)
from committime.collector_bitbucket import BitbucketCommitCollector
from committime.collector_containerimage import ContainerImageCommitCollector
from committime.collector_gitea import GiteaCommitCollector
from committime.collector_github import GitHubCommitCollector
from committime.collector_gitlab import GitLabCommitCollector
from committime.collector_image import ImageCommitCollector
from pelorus.config import (
    REDACT,
    env_var_names,
    env_vars,
    load_and_log,
    log,
    no_env_vars,
)
from pelorus.config.converters import comma_separated, pass_through
from pelorus.utils import Url

PROVIDER_CLASSES_BY_NAME = {
    "github": GitHubCommitCollector,
    "bitbucket": BitbucketCommitCollector,
    "gitea": GiteaCommitCollector,
    "azure-devops": AzureDevOpsCommitCollector,
    "gitlab": GitLabCommitCollector,
}

DEFAULT_PROVIDER = "git"

DEFAULT_COMMIT_DATE_FORMAT = "%a %b %d %H:%M:%S %Y %z"


@define(kw_only=True)
class ContainerImageCommittimeConfig:
    kube_client: DynamicClient = field(metadata=no_env_vars())

    app_label: str = pelorus.DEFAULT_APP_LABEL
    namespaces: set[str] = field(factory=set, converter=comma_separated(set))
    prod_label: str = field(default=pelorus.DEFAULT_PROD_LABEL)

    label_commit_time_format: str = field(
        default=DEFAULT_COMMIT_DATE_FORMAT, metadata=env_vars("COMMIT_DATE_FORMAT")
    )

    label_commit_time: str = field(
        default=CommitMetric._ANNOTATION_MAPPING["commit_time"],
        metadata=env_vars(COMMIT_DATE_ANNOTATION_ENV),
    )

    label_commit_hash: str = field(
        default=CommitMetric._ANNOTATION_MAPPING["commit_hash"],
        metadata=env_vars(COMMIT_HASH_ANNOTATION_ENV),
    )

    def make_collector(self) -> AbstractCommitCollector:
        return ContainerImageCommitCollector(
            kube_client=self.kube_client,
            date_format=self.label_commit_time_format,
            namespaces=self.namespaces,
            prod_label=self.prod_label,
            username="",
            token="",
            app_label=self.app_label,
            date_annotation_name=self.label_commit_time,
            hash_annotation_name=self.label_commit_hash,
        )


@define(kw_only=True)
class ImageCommittimeConfig:
    kube_client: DynamicClient = field(metadata=no_env_vars())

    app_label: str = pelorus.DEFAULT_APP_LABEL

    date_format: str = field(
        default=DEFAULT_COMMIT_DATE_FORMAT, metadata=env_vars("COMMIT_DATE_FORMAT")
    )

    date_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPING["commit_time"],
        metadata=env_vars(COMMIT_DATE_ANNOTATION_ENV),
    )

    hash_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPING["commit_hash"],
        metadata=env_vars(COMMIT_HASH_ANNOTATION_ENV),
    )

    repo_url_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPING["repo_url"],
        metadata=env_vars(COMMIT_REPO_URL_ANNOTATION_ENV),
    )

    def make_collector(self) -> AbstractCommitCollector:
        return ImageCommitCollector(
            kube_client=self.kube_client,
            date_format=self.date_format,
            username="",
            token="",
            app_label=self.app_label,
            date_annotation_name=self.date_annotation_name,
            hash_annotation_name=self.hash_annotation_name,
            repo_url_annotation_name=self.repo_url_annotation_name,
        )


@define(kw_only=True)
class GitCommittimeConfig:
    kube_client: DynamicClient = field(metadata=no_env_vars())

    username: str = field(default="", metadata=env_vars(*env_var_names.USERNAME))
    token: str = field(
        default="", metadata=env_vars(*env_var_names.TOKEN) | log(REDACT), repr=False
    )

    namespaces: set[str] = field(factory=set, converter=comma_separated(set))

    git_api: Optional[Url] = field(
        default=None,
        converter=attrs.converters.optional(pass_through(Url, Url.parse)),
        metadata=env_vars(*env_var_names.GIT_API),
    )

    git_provider: str = field(
        default=pelorus.DEFAULT_GIT,
        validator=attrs.validators.in_(PROVIDER_CLASSES_BY_NAME.keys()),
    )

    app_label: str = pelorus.DEFAULT_APP_LABEL

    tls_verify: bool = field(
        default=pelorus.DEFAULT_TLS_VERIFY, converter=attrs.converters.to_bool
    )

    hash_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPING["commit_hash"],
        metadata=env_vars(COMMIT_HASH_ANNOTATION_ENV),
    )

    repo_url_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPING["repo_url"],
        metadata=env_vars(COMMIT_REPO_URL_ANNOTATION_ENV),
    )

    def make_collector(self) -> AbstractCommitCollector:
        cls = PROVIDER_CLASSES_BY_NAME[self.git_provider]
        kwargs = dict(
            kube_client=self.kube_client,
            username=self.username,
            token=self.token,
            namespaces=self.namespaces,
            tls_verify=self.tls_verify,
            app_label=self.app_label,
            hash_annotation_name=self.hash_annotation_name,
            repo_url_annotation_name=self.repo_url_annotation_name,
        )
        if self.git_api:
            kwargs["git_api"] = self.git_api
        return cls(**kwargs)


PROVIDER_CONFIG_CLASSES = {
    "git": GitCommittimeConfig,
    "image": ImageCommittimeConfig,
    "containerimage": ContainerImageCommittimeConfig,
}


@define(kw_only=True)
class CommittimeTypeConfig:
    provider: str = field(
        default=DEFAULT_PROVIDER, validator=attrs.validators.in_(PROVIDER_CONFIG_CLASSES.keys())
    )


def set_up(prod: bool = True) -> AbstractCommitCollector:
    pelorus.setup_logging(prod=prod)
    provider_config = load_and_log(CommittimeTypeConfig)

    dyn_client = pelorus.utils.get_k8s_client()

    config_cls = PROVIDER_CONFIG_CLASSES[provider_config.provider]
    config = load_and_log(config_cls, other=dict(kube_client=dyn_client))

    collector = config.make_collector()

    REGISTRY.register(collector)
    return collector


if __name__ == "__main__":
    import logging

    try:
        set_up()
    except Exception as e:
        logging.error(
            "Failed to configure committime exporter: %s. "
            "Set GIT_PROVIDER (git/image/containerimage) "
            "and required provider settings (e.g. TOKEN, GIT_API). "
            "Starting metrics server anyway - configure and restart to collect commit data.",
            e,
            exc_info=True,
        )

    start_http_server(pelorus.EXPORTER_PORT)
    logging.info("Committime exporter ready, serving metrics on :%d", pelorus.EXPORTER_PORT)

    while True:
        time.sleep(1)

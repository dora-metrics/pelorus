#!/usr/bin/python3
import logging
import time
from typing import Optional

import attrs.converters
import attrs.validators
from attrs import define, field
from openshift.dynamic import DynamicClient
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

PROVIDER_TYPES = {"git", "image", "containerimage"}
DEFAULT_PROVIDER = "git"

DEFAULT_COMMIT_DATE_FORMAT = "%a %b %d %H:%M:%S %Y %z"


@define(kw_only=True)
class CommittimeTypeConfig:
    provider: str = field(
        default=DEFAULT_PROVIDER, validator=attrs.validators.in_(PROVIDER_TYPES)
    )


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
        default=CommitMetric._ANNOTATION_MAPPIG["commit_time"],
        metadata=env_vars(COMMIT_DATE_ANNOTATION_ENV),
    )

    label_commit_hash: str = field(
        default=CommitMetric._ANNOTATION_MAPPIG["commit_hash"],
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

    # Used to convert time and date found in the
    # Docker Label io.openshift.build.commit.date
    # or annotation for the Image
    date_format: str = field(
        default=DEFAULT_COMMIT_DATE_FORMAT, metadata=env_vars("COMMIT_DATE_FORMAT")
    )

    date_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPIG["commit_time"],
        metadata=env_vars(COMMIT_DATE_ANNOTATION_ENV),
    )

    # TODO hash_annotation_name and repo_url_annotation_name seem to be
    # unnecessary
    hash_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPIG["commit_hash"],
        metadata=env_vars(COMMIT_HASH_ANNOTATION_ENV),
    )

    repo_url_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPIG["repo_url"],
        metadata=env_vars(COMMIT_REPO_URL_ANNOTATION_ENV),
    )

    def make_collector(self) -> AbstractCommitCollector:
        # Image provider is a special case, where commit time
        # metadata is stored within image.openshift.io/v1 object
        #
        # The Image [image.openshift.io/v1] is not namespaced
        #
        # In such case no Git API call is necessary
        #
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

    # TODO hash_annotation_name and repo_url_annotation_name seem to be
    # unnecessary
    hash_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPIG["commit_hash"],
        metadata=env_vars(COMMIT_HASH_ANNOTATION_ENV),
    )

    repo_url_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPIG["repo_url"],
        metadata=env_vars(COMMIT_REPO_URL_ANNOTATION_ENV),
    )

    def __attrs_post_init__(self):
        if not (self.username and self.token):
            logging.warning(
                "No API_USER and no TOKEN given. This is okay for public repositories only."
            )
        elif (self.username and not self.token) or (not self.username and self.token):
            logging.warning(
                "username and token must both be set, or neither should be set. Unsetting both."
            )
            self.username = ""
            self.token = ""

    def make_collector(self) -> AbstractCommitCollector:
        git_provider = self.git_provider

        if git_provider == "gitlab":
            return GitLabCommitCollector(
                kube_client=self.kube_client,
                username=self.username,
                token=self.token,
                namespaces=self.namespaces,
                app_label=self.app_label,
                hash_annotation_name=self.hash_annotation_name,
                repo_url_annotation_name=self.repo_url_annotation_name,
            )
        if git_provider == "github":
            if self.git_api:
                api = dict(git_api=self.git_api)
            else:
                api = {}
            return GitHubCommitCollector(
                kube_client=self.kube_client,
                username=self.username,
                token=self.token,
                namespaces=self.namespaces,
                tls_verify=self.tls_verify,
                app_label=self.app_label,
                hash_annotation_name=self.hash_annotation_name,
                repo_url_annotation_name=self.repo_url_annotation_name,
                **api,
            )
        if git_provider == "bitbucket":
            return BitbucketCommitCollector(
                kube_client=self.kube_client,
                username=self.username,
                token=self.token,
                namespaces=self.namespaces,
                tls_verify=self.tls_verify,
                app_label=self.app_label,
                hash_annotation_name=self.hash_annotation_name,
                repo_url_annotation_name=self.repo_url_annotation_name,
            )
        if git_provider == "gitea":
            if self.git_api:
                api = dict(git_api=self.git_api)
            else:
                api = {}
            return GiteaCommitCollector(
                kube_client=self.kube_client,
                username=self.username,
                token=self.token,
                namespaces=self.namespaces,
                app_label=self.app_label,
                hash_annotation_name=self.hash_annotation_name,
                repo_url_annotation_name=self.repo_url_annotation_name,
                **api,
            )
        if git_provider == "azure-devops":
            if self.git_api:
                api = dict(git_api=self.git_api)
            else:
                api = {}
            return AzureDevOpsCommitCollector(
                kube_client=self.kube_client,
                username=self.username,
                token=self.token,
                namespaces=self.namespaces,
                app_label=self.app_label,
                hash_annotation_name=self.hash_annotation_name,
                repo_url_annotation_name=self.repo_url_annotation_name,
                **api,
            )

        raise ValueError(
            f"Unknown git_provider {git_provider}"
        )  # should be unreachable


def set_up(prod: bool = True) -> AbstractCommitCollector:
    # TODO refactor: all exporters have same structure
    pelorus.setup_logging(prod=prod)
    provider_config = load_and_log(CommittimeTypeConfig)

    dyn_client = pelorus.utils.get_k8s_client()

    if provider_config.provider == "git":
        config = load_and_log(GitCommittimeConfig, other=dict(kube_client=dyn_client))
    elif provider_config.provider == "image":
        config = load_and_log(ImageCommittimeConfig, other=dict(kube_client=dyn_client))
    elif provider_config.provider == "containerimage":
        config = load_and_log(
            ContainerImageCommittimeConfig, other=dict(kube_client=dyn_client)
        )
    else:
        raise ValueError(
            f"Unknown provider {provider_config.provider}"
        )  # should be unreachable

    collector = config.make_collector()

    REGISTRY.register(collector)
    return collector


if __name__ == "__main__":
    set_up()
    # TODO refactor: create function, all exporters have same structure
    start_http_server(8080)

    while True:
        time.sleep(1)

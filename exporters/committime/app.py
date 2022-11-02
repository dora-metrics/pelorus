#!/usr/bin/python3
import logging
import time

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
    AbstractCommitCollector,
)
from committime.collector_bitbucket import BitbucketCommitCollector
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

PROVIDER_TYPES = {"git", "image"}
DEFAULT_PROVIDER = "git"

DEFAULT_COMMIT_DATE_FORMAT = "%a %b %d %H:%M:%S %Y %z"


@define(kw_only=True)
class CommittimeTypeConfig:

    provider: str = field(
        default=DEFAULT_PROVIDER, validator=attrs.validators.in_(PROVIDER_TYPES)
    )


@define(kw_only=True)
class ImageCommittimeConfig:
    kube_client: DynamicClient = field(metadata=no_env_vars())

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
        )


@define(kw_only=True)
class GitCommittimeConfig:
    kube_client: DynamicClient = field(metadata=no_env_vars())

    username: str = field(default="", metadata=env_vars(*env_var_names.USERNAME))
    token: str = field(
        default="", metadata=env_vars(*env_var_names.TOKEN) | log(REDACT), repr=False
    )

    namespaces: set[str] = field(factory=set, converter=comma_separated(set))

    git_api: Url | None = field(
        default=None,
        converter=attrs.converters.optional(pass_through(Url, Url.parse)),
        metadata=env_vars(*env_var_names.GIT_API),
    )

    git_provider: str = field(
        default=pelorus.DEFAULT_GIT,
        validator=attrs.validators.in_(PROVIDER_CLASSES_BY_NAME.keys()),
    )

    tls_verify: bool = field(
        default=pelorus.DEFAULT_TLS_VERIFY, converter=attrs.converters.to_bool
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
                **api,
            )
        if git_provider == "bitbucket":
            return BitbucketCommitCollector(
                kube_client=self.kube_client,
                username=self.username,
                token=self.token,
                namespaces=self.namespaces,
                tls_verify=self.tls_verify,
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
                **api,
            )
        if git_provider == "azure-devops":
            return AzureDevOpsCommitCollector(
                kube_client=self.kube_client,
                username=self.username,
                token=self.token,
                namespaces=self.namespaces,
                git_api=self.git_api,
            )

        raise ValueError(
            f"Unknown git_provider {git_provider}"
        )  # should be unreachable


if __name__ == "__main__":
    pelorus.setup_logging()
    provider_config = load_and_log(CommittimeTypeConfig)

    dyn_client = pelorus.utils.get_k8s_client()

    if provider_config.provider == "git":
        config = load_and_log(GitCommittimeConfig, other=dict(kube_client=dyn_client))
    elif provider_config.provider == "image":
        config = load_and_log(ImageCommittimeConfig, other=dict(kube_client=dyn_client))
    else:
        raise ValueError(
            f"Unknown provider {provider_config.provider}"
        )  # should be unreachable

    collector = config.make_collector()

    REGISTRY.register(collector)
    start_http_server(8080)

    while True:
        time.sleep(1)

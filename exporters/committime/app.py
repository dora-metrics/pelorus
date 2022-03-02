#!/usr/bin/python3
import logging
import os
import time
from distutils.util import strtobool

from committime.collector_azure_devops import AzureDevOpsCommitCollector
from committime.collector_bitbucket import BitbucketCommitCollector
from committime.collector_gitea import GiteaCommitCollector
from committime.collector_github import GitHubCommitCollector
from committime.collector_gitlab import GitLabCommitCollector
from kubernetes import client
from openshift.dynamic import DynamicClient
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

import pelorus


class GitFactory:
    @staticmethod
    def getCollector(
        kube_client, username, token, namespaces, apps, git_api, git_provider
    ):
        if git_provider == "gitlab":
            return GitLabCommitCollector(kube_client, username, token, namespaces, apps)
        if git_provider == "github":
            return GitHubCommitCollector(
                kube_client, username, token, namespaces, apps, git_api, tls_verify
            )
        if git_provider == "bitbucket":
            return BitbucketCommitCollector(
                kube_client, username, token, namespaces, apps
            )
        if git_provider == "gitea":
            return GiteaCommitCollector(
                kube_client, username, token, namespaces, apps, git_api
            )
        if git_provider == "azure-devops":
            return AzureDevOpsCommitCollector(
                kube_client, username, token, namespaces, apps, git_api
            )


if __name__ == "__main__":
    pelorus.upgrade_legacy_vars()

    pelorus.load_kube_config()
    k8s_config = client.Configuration()
    k8s_client = client.api_client.ApiClient(configuration=k8s_config)
    dyn_client = DynamicClient(k8s_client)

    username = os.environ.get("GIT_USER", "")
    token = os.environ.get("GIT_TOKEN", "")
    if not username and not token:
        logging.info(
            "No GIT_USER and no GIT_TOKEN given. This is okay for public repositories only."
        )
    git_api = os.environ.get("GIT_API")
    git_provider = os.environ.get("GIT_PROVIDER", pelorus.DEFAULT_GIT)
    tls_verify = bool(
        strtobool(os.environ.get("TLS_VERIFY", pelorus.DEFAULT_TLS_VERIFY))
    )
    namespaces = None
    if os.environ.get("NAMESPACES") is not None:
        namespaces = [proj.strip() for proj in os.environ.get("NAMESPACES").split(",")]
    apps = None
    start_http_server(8080)

    collector = GitFactory.getCollector(
        dyn_client, username, token, namespaces, apps, git_api, git_provider
    )
    REGISTRY.register(collector)

    while True:
        time.sleep(1)

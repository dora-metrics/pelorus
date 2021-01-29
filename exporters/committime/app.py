#!/usr/bin/python3
from collector_bitbucket import BitbucketCommitCollector
from collector_gitlab import GitLabCommitCollector
from collector_github import GitHubCommitCollector
import os
import pelorus
import sys
import time
from util import dict2obj
from kubernetes import client
from openshift.dynamic import DynamicClient
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

REQUIRED_CONFIG = ['GIT_USER', 'GIT_TOKEN']


class GitFactory:
    @staticmethod
    def get_collector(kube_client, git_provider_info, exporter_opts):
        """
        Creates a collector based on the Git Provider and exporter options
        :param kube_client: k8s client
        :param git_provider_info: object containing information about the Git provider
        :param exporter_opts: exporter specific options
        """
        if git_provider_info.git_provider == "gitlab":
            return GitLabCommitCollector(kube_client, git_provider_info, exporter_opts)
        if git_provider_info.git_provider == "github":
            return GitHubCommitCollector(kube_client, git_provider_info, exporter_opts)
        if git_provider_info.git_provider == "bitbucket":
            return BitbucketCommitCollector(kube_client, git_provider_info, exporter_opts)


def git_provider():
    """
    Returns the Git provider info to be used for the collector
    :return: GitProviderInfo object
    """
    return dict2obj({
        'username': os.getenv('GIT_USER'),
        'token': os.getenv('GIT_TOKEN'),
        'git_api': os.getenv('GIT_API'),
        'git_provider': os.getenv('GIT_PROVIDER', pelorus.DEFAULT_GIT)
    })


def exporter_options():
    """
    Returns the options associated with this exporter
    :return: ExporterOptions object
    """
    namespaces = None
    if os.getenv('NAMESPACES') is not None:
        namespaces = [proj.strip() for proj in os.getenv('NAMESPACES').split(",")]
    return dict2obj({
        'namespaces': namespaces,
        'apps': None,
        'no_image_stream': str(os.getenv('NO_IMAGE_STREAM', False)).lower() == "true".lower()
    })


if __name__ == "__main__":
    pelorus.upgrade_legacy_vars()
    if pelorus.missing_configs(REQUIRED_CONFIG):
        print("This program will exit.")
        sys.exit(1)

    pelorus.load_kube_config()
    k8s_config = client.Configuration()
    k8s_client = client.api_client.ApiClient(configuration=k8s_config)
    dyn_client = DynamicClient(k8s_client)

    collector = GitFactory.get_collector(dyn_client, git_provider(), exporter_options())
    start_http_server(8080)
    REGISTRY.register(collector)

    while True:
        time.sleep(1)

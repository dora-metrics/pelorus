#!/usr/bin/python3
from collector_bitbucket import BitbucketCommitCollector
from collector_gitlab import GitLabCommitCollector
from collector_github import GitHubCommitCollector
import os
import pelorus
import time
from kubernetes import client
from openshift.dynamic import DynamicClient
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

REQUIRED_CONFIG = ['GITHUB_USER', 'GITHUB_TOKEN']

pelorus.load_kube_config()
k8s_config = client.Configuration()
k8s_client = client.api_client.ApiClient(configuration=k8s_config)
dyn_client = DynamicClient(k8s_client)


class GitFactory:
    @staticmethod
    def getCollector(username, token, namespaces, apps, git_api, git_type):
        if git_type == "gitlab":
            return GitLabCommitCollector("", "", "", "")
        if git_type == "github":
            return GitHubCommitCollector(username, token, namespaces, apps, git_api)
        if git_type == "bitbucket":
            return BitbucketCommitCollector("", "", "", "")


if __name__ == "__main__":
    pelorus.check_required_config(REQUIRED_CONFIG)
    username = os.environ.get('GITHUB_USER')
    token = os.environ.get('GITHUB_TOKEN')
    git_api = os.environ.get('GITHUB_API')
    git_type = os.environ.get('GIT_TYPE')
    namespaces = None
    if os.environ.get('NAMESPACES') is not None:
        namespaces = [proj.strip() for proj in os.environ.get('NAMESPACES').split(",")]
    apps = None
    start_http_server(8080)

    collector = GitFactory.getCollector(username, token, namespaces, apps, git_api, git_type)
    REGISTRY.register(collector)

    while True:
        time.sleep(1)

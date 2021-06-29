from pprint import pprint

import pytest
from kubernetes.client import ApiClient, Configuration
from openshift.dynamic import DynamicClient

from committime.collector_github import GitHubCommitCollector

# export GIT_USER=gituser
# export GIT_TOKEN=gittoken
# export GIT_API=localhost:3000
# export LOG_LEVEL=DEBUG
# export NAMESPACES=basic-nginx-build,basic-nginx-dev,basic-nginx-stage,basic-nginx-prod
# export TLS_VERIFY=False


def setup_collector():
    kube_config = Configuration()
    kube_config.host = "https://localhost:3000"
    kube_config.verify_ssl = False
    dyn_client = DynamicClient(ApiClient(configuration=kube_config))

    username = "gituser"
    token = "gittoken"
    git_api = "https://localhost:3000"
    namespaces = (
        "basic-nginx-build,basic-nginx-dev,basic-nginx-stage,basic-nginx-prod".split(
            ","
        )
    )
    apps = None
    tls_verify = False
    return GitHubCommitCollector(
        dyn_client, username, token, namespaces, apps, git_api, tls_verify
    )


@pytest.mark.integration
def test_github_collector():
    collector = setup_collector()

    metrics = collector.generate_metrics()
    pprint(metrics)

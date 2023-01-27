import pytest
from kubernetes.client import ApiClient, Configuration
from openshift.dynamic import DynamicClient


@pytest.fixture
def openshift_client() -> DynamicClient:
    kube_config = Configuration()
    kube_config.host = "https://localhost:3000"
    kube_config.verify_ssl = False
    return DynamicClient(ApiClient(configuration=kube_config))

import pytest
from openshift.dynamic import DynamicClient

from committime import CommitMetric
from committime.collector_bitbucket import BitbucketCommitCollector


@pytest.fixture
def bitbucket_collector(openshift_client: DynamicClient):
    return BitbucketCommitCollector(
        kube_client=openshift_client,
        username="",
        token="",
        namespaces=set(),
        tls_verify=False,
    )


@pytest.mark.mockoon
@pytest.mark.skip(
    reason="Must improve mockoon automation first-- "
    "only works with one environment, and not on macOS."
)
def test_time_retrieval(bitbucket_collector: BitbucketCommitCollector):
    metric = CommitMetric("fake_app")
    metric.repo_url = "http://127.0.0.1:3001/kgranger-rh2/bitbucket-committime-test"
    metric.commit_hash = "1766a75de2be5cf7fc6bf1fb8424b6a9100485e4"

    EXPECTED_TIMESTAMP = 1665100072

    bitbucket_collector.get_commit_time(metric)

    assert metric.commit_timestamp == EXPECTED_TIMESTAMP

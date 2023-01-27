from typing import cast

import pytest
from openshift.dynamic import DynamicClient

from committime.app import ImageCommittimeConfig
from committime.collector_image import ImageCommitCollector
from pelorus.config import load_and_log


@pytest.fixture
def image_collector(openshift_client: DynamicClient) -> ImageCommitCollector:
    config = load_and_log(
        ImageCommittimeConfig, other=dict(kube_client=openshift_client), env={}
    )
    collector = config.make_collector()

    return cast(ImageCommitCollector, collector)


EXPECTED_TIME_STR = "Tue Jan 03 22:53:46 2023 +0000"
EXPECTED_TIMESTAMP = int(1672786426.076646)


@pytest.mark.mockoon
def test_image_collector(image_collector: ImageCommitCollector):
    metrics = list(image_collector.generate_metrics())

    # there should only be two metrics:
    # one where the info came from the docker label,
    # and one where it came from the annotation.
    # both have the same time for simplicity's sake.

    # the others are missing necessary data and should not appear.

    assert len(metrics) == 2

    for metric in metrics:
        assert metric.commit_time == EXPECTED_TIME_STR
        assert metric.commit_timestamp is not None
        assert int(metric.commit_timestamp) == EXPECTED_TIMESTAMP

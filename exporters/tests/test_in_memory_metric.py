#
# Copyright Red Hat
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#


from unittest import mock

import pytest
from prometheus_client import REGISTRY
from prometheus_client.registry import Collector

from webhook.models.pelorus_webhook import CommitTimePelorusPayload, PelorusPayload
from webhook.store.in_memory_metric import (
    PelorusGaugeMetricFamily,
    _pelorus_metric_to_dict,
    pelorus_metric_to_prometheus,
)

metric_labels = list(_pelorus_metric_to_dict(CommitTimePelorusPayload).keys())

in_memory_test_committime_metrics = PelorusGaugeMetricFamily(
    "test_committime_metrics",
    "Test timestamp",
    labels=metric_labels,
)


@pytest.fixture(autouse=True)
def _clean_metrics():
    """Reset shared gauge metric family between tests to prevent state leakage."""
    in_memory_test_committime_metrics.samples.clear()
    in_memory_test_committime_metrics.added_metrics.clear()
    yield
    in_memory_test_committime_metrics.samples.clear()
    in_memory_test_committime_metrics.added_metrics.clear()


class CustomCommitCollector(Collector):
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        # make sure __hash__ is something prometheus' registry can handle properly.
        cls.__hash__ = lambda self: id(self)  # type: ignore

    def collect(self) -> PelorusGaugeMetricFamily:
        yield in_memory_test_committime_metrics


@pytest.fixture
def _registered_collector():
    collector = CustomCommitCollector()
    REGISTRY.register(collector)
    yield collector
    REGISTRY.unregister(collector)


def test_pelorus_gauge_metric_family(_registered_collector):
    """
    Verifies if the metric passed to the pelorus_metric_to_prometheus method
    and then registered in our CustomCommitCollector is properly collected
    by Prometheus. It does it by getting sample value and comparing the
    timestamp of that metric to the timestamp of the data received from
    Prometheus.
    """
    name = "todolist"
    timestamp = "1700000000"
    image_hash = "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d"
    namespace = "mynamespace"
    commit_hash = "5379bad65a3f83853a75aabec9e0e43c75fd18fc"
    commit_payload = CommitTimePelorusPayload(
        app=name,
        timestamp=timestamp,
        image_sha=image_hash,
        namespace=namespace,
        commit_hash=commit_hash,
    )

    prometheus_commit_metric = pelorus_metric_to_prometheus(commit_payload)
    in_memory_test_committime_metrics.add_metric(
        commit_payload.commit_hash,
        prometheus_commit_metric,
        commit_payload.timestamp,
    )

    query_labels = {
        "app": f"/{name}/",
        "image_sha": image_hash,
        "commit": commit_hash,
        "namespace": namespace,
    }

    query_result = REGISTRY.get_sample_value(
        "test_committime_metrics",
        labels=query_labels,
    )

    assert query_result == float(timestamp)


def test_all_models_have_prometheus_mappings():
    """Ensure all PelorusPayload subclasses have non-empty Prometheus mappings."""
    import webhook.models.pelorus_webhook as pelorus_webhook

    test_models = []

    for cls in pelorus_webhook.__dict__.values():
        if isinstance(cls, type) and issubclass(cls, PelorusPayload):
            test_models.append(cls)

    for test_model in test_models:
        metric = _pelorus_metric_to_dict(test_model)
        assert isinstance(metric, dict) and len(metric) > 0, (
            f"{test_model.__name__} returned empty or non-dict Prometheus mapping"
        )
        for key, value in metric.items():
            assert isinstance(key, str) and isinstance(value, str), (
                f"{test_model.__name__} mapping has non-string key or value: {key!r}={value!r}"
            )


class NewPelorusPayloadModel(PelorusPayload):
    pass


def test_model_does_not_have_prometheus_mapping():
    """Ensure TypeError is raised for PelorusPayload subclasses without Prometheus mappings."""

    with pytest.raises(TypeError) as type_error:
        _pelorus_metric_to_dict(NewPelorusPayloadModel)
    assert "Unsupported Prometheus data model" in str(type_error.value)


@mock.patch(
    "webhook.store.in_memory_metric._pelorus_metric_to_dict",
    return_value={"app": "nonexisting"},
)
def test_model_missing_value_in_model(_mock_metric_to_dict):
    """Ensure TypeError is raised when Prometheus mapping references attributes not present in the model."""

    with pytest.raises(TypeError) as type_error:
        pelorus_metric_to_prometheus(NewPelorusPayloadModel)
    assert "Attribute nonexisting was not found in" in str(type_error.value)

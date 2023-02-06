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

metric_labels = list(_pelorus_metric_to_dict(CommitTimePelorusPayload).values())

in_memory_test_committime_metrics = PelorusGaugeMetricFamily(
    "test_committime_metrics",
    "Test timestamp",
    labels=metric_labels,
)


class CustomCommitCollector(Collector):
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        # make sure __hash__ is something prometheus' registry can handle properly.
        cls.__hash__ = lambda self: id(self)  # type: ignore

    def collect(self) -> PelorusGaugeMetricFamily:
        yield in_memory_test_committime_metrics


class TestInMemoryMetric:
    def setup_method(self):
        self.custom_collector = CustomCommitCollector()
        REGISTRY.register(self.custom_collector)

    def teardown_method(self):
        REGISTRY.unregister(self.custom_collector)

    @pytest.mark.parametrize(
        "name,timestamp,image_hash,namespace,commit_hash",
        [
            (
                "todolist",
                "timestamp_str",
                "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
                "mynamespace",
                "5379bad65a3f83853a75aabec9e0e43c75fd18fc",
            ),
        ],
    )
    def test_pelorus_gauge_metric_family(
        self, name, timestamp, image_hash, namespace, commit_hash
    ):
        """
        Verifies if the metric passed to the pelorus_metric_to_prometheus method
        and then registered in our CustomCommitCollector is properly collected
        by Prometheus. It does it by getting sample value and comparing the
        timestamp of that metric to the timestamp of the data received from
        Prometheus.
        """
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

        metric_labels = {
            "app": name,
            "image_sha": image_hash,
            "commit_hash": commit_hash,
            "namespace": namespace,
        }

        query_result = REGISTRY.get_sample_value(
            "test_committime_metrics",
            labels=metric_labels,
        )

        assert query_result == timestamp


def test_all_models_have_prometheus_mappings():
    """
    Safeguard test to ensure new PelorusPayload models also have
    corresponding Prometheus model.

    It does this by verifying if all models which are inheriting
    from PelorusPayload class returns non empty dictionary from the
    _pelorus_metric_to_dict method, where the mappings are defined.

    We need to test this scenario to ensure we know how to store
    each of the Pelorus data models into Prometheus.
    """
    import webhook.models.pelorus_webhook as pelorus_webhook

    test_models = []

    for cls in pelorus_webhook.__dict__.values():
        if isinstance(cls, type) and issubclass(cls, PelorusPayload):
            test_models.append(cls)

    for test_model in test_models:
        metric = _pelorus_metric_to_dict(test_model)
        assert bool(metric)  # dict should not be empty


class NewPelorusPayloadModel(PelorusPayload):
    pass


def test_model_do_not_have_prometheus_mapping():
    """
    Negative safeguard test to ensure that proper Error is raised
    when the new models which are inheriting from PelorusPayload
    model do not have corresponding Prometheus model defined in
    the _pelorus_metric_to_dict method.
    """

    with pytest.raises(TypeError) as type_error:
        _pelorus_metric_to_dict(NewPelorusPayloadModel)
    assert "Improper prometheus data model" in str(type_error.value)


@mock.patch(
    "webhook.store.in_memory_metric._pelorus_metric_to_dict",
    return_value={"app": "nonexisting"},
)
def test_model_missing_value_in_model(*args):
    """
    Negative safeguard test to ensure that the model which is
    inheriting from the PelorusPayload  model does match
    expected Prometheus model defined in the _pelorus_metric_to_dict
    method.

    It does this by verifying if all the expected variables are defined
    in the PelorusPayload model, otherwise raising TypeError.
    """

    with pytest.raises(TypeError) as type_error:
        pelorus_metric_to_prometheus(NewPelorusPayloadModel)
    assert "Attribute nonexisting was not found in" in str(type_error.value)

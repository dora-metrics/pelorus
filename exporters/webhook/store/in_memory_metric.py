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

import threading
from typing import Dict, Optional, Sequence, Union

from prometheus_client.core import GaugeMetricFamily
from pydantic.main import ModelMetaclass

from provider_common import format_app_name
from webhook.models.pelorus_webhook import (
    CommitTimePelorusPayload,
    DeployTimePelorusPayload,
    FailurePelorusPayload,
    PelorusPayload,
)


def _pelorus_metric_to_dict(
    pelorus_model: Union[PelorusPayload, ModelMetaclass]
) -> Dict[str, str]:
    """
    Mapping between Pelorus Payload Metrics defined as pydantic classes and the
    Prometheus expected metrics.

    Attributes:
        pelorus_model Union(PelorusPayloadType, ModelMetaclass): imported
                        class that is subclass of the PelorusPayload.
                        This can be either class or it's instance.

    Returns:
        Dict[str, str]: First item is the Prometheus expected label and second
                        the name of the value from the PelorusPayload model.

    Raises:
        TypeError: If the prometheus data model is not supported
    """
    pelorus_payload = {"app": "app"}

    failure_payload = {
        **pelorus_payload,
        "issue_number": "failure_id",
    }

    deploytime_payload = {
        **pelorus_payload,
        "namespace": "namespace",
        "image_sha": "image_sha",
    }

    committime_payload = {
        **deploytime_payload,
        "commit": "commit_hash",
    }

    class_model_name_to_dict = {
        "PelorusPayload": pelorus_payload,
        "FailurePelorusPayload": failure_payload,
        "DeployTimePelorusPayload": deploytime_payload,
        "CommitTimePelorusPayload": committime_payload,
    }

    # This is to use model name, which equals to the
    # class name. The __class_ can't be used here as
    # it's inherited from pydantic.main.ModelMetaclass
    if hasattr(pelorus_model, "__qualname__"):
        model_name = pelorus_model.__qualname__
    else:
        # It's an instance
        model_name = pelorus_model.__class__.__qualname__

    pelorus_model_to_prometheus_mapping = class_model_name_to_dict.get(model_name)

    if pelorus_model_to_prometheus_mapping:
        return pelorus_model_to_prometheus_mapping

    raise TypeError(f"Improper prometheus data model: {model_name}")


def pelorus_metric_to_prometheus(pelorus_model: PelorusPayload) -> list[str]:
    """
    Returns prometheus metrics directly from the PelorusPayload objects.

    Attributes:
        pelorus_model PelorusPayloadType: object from which the prometheus
            data will be created.

    Returns:
        list[str]: List to be used as prometheus data.

    Raises:
        TypeError: If the expected data model did not match provided pelorus_model
    """
    data_model = _pelorus_metric_to_dict(pelorus_model)
    data_values = []

    for metric_value in data_model.values():
        if hasattr(pelorus_model, metric_value):
            value = getattr(pelorus_model, metric_value)
            if metric_value == "app":
                data_values.append(format_app_name(value))
            else:
                data_values.append(value)
        else:
            # If the model do not match the payload dict, we should raise an error
            raise TypeError(
                f"Attribute {metric_value} was not found in the {pelorus_model.__class__.__qualname__} metric model"
            )
    return data_values


class PelorusGaugeMetricFamily(GaugeMetricFamily):
    """
    Wrapper around GaugeMetricFamily class which allows to async
    access to it's data when used by different webhook endpoints.
    """

    def __init__(
        self,
        name: str,
        documentation: str,
        value: Optional[float] = None,
        labels: Optional[Sequence[str]] = None,
        unit: str = "",
    ):
        super().__init__(name, documentation, value, labels, unit)
        self.lock = threading.Lock()
        self.added_metrics = set()

    def add_metric(self, metric_id, *args, **kwargs):
        with self.lock:
            if metric_id and metric_id not in self.added_metrics:
                super().add_metric(*args, **kwargs)
                self.added_metrics.add(metric_id)

    def __iter__(self, *args, **kwargs):
        with self.lock:
            for item in super().__iter__(*args, **kwargs):
                yield item


in_memory_commit_metrics = PelorusGaugeMetricFamily(
    "commit_timestamp",
    "Commit timestamp",
    labels=list(_pelorus_metric_to_dict(CommitTimePelorusPayload).values()),
)

in_memory_deploy_timestamp_metric = PelorusGaugeMetricFamily(
    "deploy_timestamp",
    "Deployment timestamp",
    labels=list(_pelorus_metric_to_dict(DeployTimePelorusPayload).values()),
)

in_memory_failure_creation_metric = PelorusGaugeMetricFamily(
    "failure_creation_timestamp",
    "Failure Creation Timestamp",
    labels=list(_pelorus_metric_to_dict(FailurePelorusPayload).values()),
)
in_memory_failure_resolution_metric = PelorusGaugeMetricFamily(
    "failure_resolution_timestamp",
    "Failure Resolution Timestamp",
    labels=list(_pelorus_metric_to_dict(FailurePelorusPayload).values()),
)

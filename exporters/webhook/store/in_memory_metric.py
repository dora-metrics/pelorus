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

import logging
import os as _os
import threading
import time as _time
from collections import OrderedDict, deque
from typing import Optional, Sequence, Union

from prometheus_client import Gauge
from prometheus_client.core import GaugeMetricFamily
from provider_common import format_app_name
from webhook.models.pelorus_webhook import (
    CommitTimePelorusPayload,
    DeployTimePelorusPayload,
    FailurePelorusPayload,
    PelorusPayload,
)


_PELORUS_PAYLOAD = {"app": "app"}

_FAILURE_PAYLOAD = {
    **_PELORUS_PAYLOAD,
    "issue_number": "failure_id",
}

_DEPLOYTIME_PAYLOAD = {
    **_PELORUS_PAYLOAD,
    "namespace": "namespace",
    "image_sha": "image_sha",
}

_COMMITTIME_PAYLOAD = {
    **_DEPLOYTIME_PAYLOAD,
    "commit": "commit_hash",
}

_CLASS_TO_LABEL_MAP: dict[type, dict[str, str]] = {
    PelorusPayload: _PELORUS_PAYLOAD,
    FailurePelorusPayload: _FAILURE_PAYLOAD,
    DeployTimePelorusPayload: _DEPLOYTIME_PAYLOAD,
    CommitTimePelorusPayload: _COMMITTIME_PAYLOAD,
}


def _pelorus_metric_to_dict(
    pelorus_model: Union[PelorusPayload, type[PelorusPayload]]
) -> dict[str, str]:
    """
    Mapping between Pelorus Payload Metrics defined as pydantic classes and the
    Prometheus expected metrics.

    Args:
        pelorus_model: A PelorusPayload subclass or instance.

    Returns:
        dict[str, str]: First item is the Prometheus expected label and second
                        the name of the value from the PelorusPayload model.

    Raises:
        TypeError: If the prometheus data model is not supported
    """
    cls = pelorus_model if isinstance(pelorus_model, type) else type(pelorus_model)

    result = _CLASS_TO_LABEL_MAP.get(cls)
    if result is not None:
        return result

    raise TypeError(f"Unsupported Prometheus data model: {cls.__name__}")


_ATTR_SENTINEL = object()


def pelorus_metric_to_prometheus(pelorus_model: PelorusPayload) -> list[str]:
    """
    Returns prometheus metrics directly from the PelorusPayload objects.

    Args:
        pelorus_model: PelorusPayload instance from which prometheus
            data will be created.

    Returns:
        list[str]: List to be used as prometheus data.

    Raises:
        TypeError: If the expected data model did not match provided pelorus_model
    """
    data_model = _pelorus_metric_to_dict(pelorus_model)
    data_values = []

    for metric_value in data_model.values():
        value = getattr(pelorus_model, metric_value, _ATTR_SENTINEL)
        if value is _ATTR_SENTINEL:
            raise TypeError(
                f"Attribute {metric_value} was not found in the {pelorus_model.__class__.__qualname__} metric model"
            )
        if metric_value == "app":
            data_values.append(format_app_name(value))
        else:
            data_values.append(value)
    return data_values


_max_metrics_raw = _os.environ.get("PELORUS_WEBHOOK_MAX_METRICS", "10000")
try:
    _MAX_METRICS = int(_max_metrics_raw)
except ValueError:
    raise ValueError(
        f"PELORUS_WEBHOOK_MAX_METRICS must be an integer, got: {_max_metrics_raw!r}"
    )
if _MAX_METRICS < 1:
    raise ValueError(
        f"PELORUS_WEBHOOK_MAX_METRICS must be >= 1, got: {_MAX_METRICS}"
    )

_store_utilization = Gauge(
    "pelorus_webhook_store_utilization",
    "Number of metrics currently held in the in-memory webhook store",
    ["metric_family"],
)


class PelorusGaugeMetricFamily(GaugeMetricFamily):
    """
    Wrapper around GaugeMetricFamily class which allows thread-safe
    access to its data when used by different webhook endpoints.
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
        self.samples = deque(self.samples)
        self.lock = threading.Lock()
        self.added_metrics: OrderedDict[str, None] = OrderedDict()
        self._utilization_gauge = _store_utilization.labels(metric_family=name)
        self._last_full_warning: float = 0.0
        self._full_drops_since_warning: int = 0

    _FULL_WARNING_INTERVAL = 60.0

    def add_metric(self, metric_id, *args, **kwargs):
        with self.lock:
            if metric_id and metric_id not in self.added_metrics:
                if len(self.added_metrics) >= _MAX_METRICS:
                    self._full_drops_since_warning += 1
                    now = _time.monotonic()
                    if now - self._last_full_warning >= self._FULL_WARNING_INTERVAL:
                        logging.warning(
                            "In-memory metric store full (%d), dropped %d oldest entries since last warning",
                            _MAX_METRICS,
                            self._full_drops_since_warning,
                        )
                        self._last_full_warning = now
                        self._full_drops_since_warning = 0
                    self.added_metrics.popitem(last=False)
                    if self.samples:
                        self.samples.popleft()
                super().add_metric(*args, **kwargs)
                self.added_metrics[metric_id] = None
                self._utilization_gauge.set(len(self.added_metrics))

    @property
    def metric_count(self) -> int:
        with self.lock:
            return len(self.added_metrics)

    def __iter__(self):
        with self.lock:
            snapshot = list(super().__iter__())
        return iter(snapshot)


in_memory_commit_metrics = PelorusGaugeMetricFamily(
    "commit_timestamp",
    "Commit timestamp",
    labels=list(_pelorus_metric_to_dict(CommitTimePelorusPayload).keys()),
)

in_memory_deploy_timestamp_metric = PelorusGaugeMetricFamily(
    "deploy_timestamp",
    "Deployment timestamp",
    labels=list(_pelorus_metric_to_dict(DeployTimePelorusPayload).keys()),
)

in_memory_failure_creation_metric = PelorusGaugeMetricFamily(
    "failure_creation_timestamp",
    "Failure Creation Timestamp",
    labels=list(_pelorus_metric_to_dict(FailurePelorusPayload).keys()),
)
in_memory_failure_resolution_metric = PelorusGaugeMetricFamily(
    "failure_resolution_timestamp",
    "Failure Resolution Timestamp",
    labels=list(_pelorus_metric_to_dict(FailurePelorusPayload).keys()),
)

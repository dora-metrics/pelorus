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

import time

import pytest
from pydantic import BaseModel, ValidationError

from webhook.models.pelorus_webhook import (
    CommitTimePelorusPayload,
    DeployTimePelorusPayload,
    FailurePelorusPayload,
    PelorusDeliveryHeaders,
    PelorusMetric,
    PelorusMetricSpec,
    PelorusPayload,
)


def _make_payloads():
    ts = int(time.time())
    payload = {"app": "todolist", "timestamp": ts}
    deploy = {
        **payload,
        "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
        "namespace": "mynamespace",
    }
    commit = {**deploy, "commit_hash": "abc123f"}
    failure = {**payload, "failure_id": "test", "failure_event": "created"}
    return ts, payload, deploy, commit, failure


@pytest.mark.parametrize(
    "event_type",
    ["committime", "deploytime", "failure", "ping"],
)
def test_pelorus_delivery_headers_valid_event(event_type):
    headers = PelorusDeliveryHeaders(**{"x-pelorus-event": event_type})
    assert headers.event_type == PelorusMetricSpec(event_type)


@pytest.mark.parametrize(
    "event_type",
    ["unsupported", "commit", "", "COMMITTIME"],
)
def test_pelorus_delivery_headers_invalid_event(event_type):
    with pytest.raises(ValidationError):
        PelorusDeliveryHeaders(**{"x-pelorus-event": event_type})


@pytest.mark.parametrize(
    "signature",
    [
        "sha256=" + "a" * 64,
        "sha256=" + "0123456789abcdef" * 4,
    ],
)
def test_pelorus_delivery_headers_valid_signature(signature):
    headers = PelorusDeliveryHeaders(
        **{"x-pelorus-event": "committime", "x-hub-signature-256": signature}
    )
    assert headers.x_hub_signature_256 == signature


def test_pelorus_delivery_headers_no_signature():
    headers = PelorusDeliveryHeaders(**{"x-pelorus-event": "committime"})
    assert headers.x_hub_signature_256 is None


@pytest.mark.parametrize(
    "signature",
    [
        "sha256=" + "x" * 64,  # non-hex characters
        "sha256=" + "a" * 63,  # too short
        "sha256=" + "a" * 65,  # too long
        "sha512=" + "a" * 64,  # wrong algorithm
        "a" * 64,  # missing algorithm prefix
        "improper",  # completely wrong format
    ],
)
def test_pelorus_delivery_headers_invalid_signature(signature):
    with pytest.raises(ValidationError):
        PelorusDeliveryHeaders(
            **{"x-pelorus-event": "committime", "x-hub-signature-256": signature}
        )


class FakePelorusPayload(BaseModel):
    timestamp: int
    app: str
    image_sha: str
    namespace: str


@pytest.mark.parametrize(
    "app",
    [
        "123456",
        "todolist",
    ],
)
def test_pelorus_payload_success(app):
    """Valid app and timestamp values create a PelorusPayload successfully."""
    payload = PelorusPayload(app=app, timestamp=int(time.time()))
    assert payload.get_metric_model_name() == "PelorusPayload"


@pytest.mark.parametrize(
    "app,timestamp",
    [
        (123456, 123457890),
        ("todolist", "123456789"),
        ("todolist", 12345678901),
        ("todolist", "Mon Mar 6 15:31:32 2023 +0100"),
        ("todolist", 1262307660),
        ("todolist", 2840144462),
        ("todolist", None),
        ("todolist", [1678269658]),
        ("todolist", 123.456),
    ],
)
def test_pelorus_wrong_timestamp(app, timestamp):
    """Invalid timestamps are rejected by PelorusPayload validation."""
    with pytest.raises(ValidationError):
        PelorusPayload(app=app, timestamp=timestamp)


@pytest.mark.parametrize(
    "app,timestamp",
    [
        # Test for too long app name (200 characters limit)
        ("a" * 201, "timestamp_str"),
        # Test for too long timestamp (50 characters limit)
        ("todolist", "a" * 51),
    ],
)
def test_pelorus_payload_error(app, timestamp):
    with pytest.raises(ValidationError):
        PelorusPayload(app=app, timestamp=timestamp)


@pytest.mark.parametrize(
    "failure_id,failure_event",
    [
        ("Issue-1", FailurePelorusPayload.FailureEvent.CREATED),
        ("Issue-1", FailurePelorusPayload.FailureEvent.RESOLVED),
    ],
)
def test_failure_pelorus_payload_success(failure_id, failure_event):
    """Valid failure_id and failure_event create a FailurePelorusPayload."""
    _, test_payload, _, _, _ = _make_payloads()
    payload = FailurePelorusPayload(
        **test_payload,
        failure_id=failure_id,
        failure_event=failure_event,
    )
    assert payload.failure_event in ["created", "resolved"]
    assert payload.get_metric_model_name() == "FailurePelorusPayload"


@pytest.mark.parametrize("failure_id,failure_event", [("Issue-1", "Other")])
def test_failure_pelorus_payload_error(failure_id, failure_event):
    _, test_payload, _, _, _ = _make_payloads()
    with pytest.raises(ValidationError):
        FailurePelorusPayload(
            **test_payload,
            failure_id=failure_id,
            failure_event=failure_event,
        )


@pytest.mark.parametrize(
    "image_sha,namespace",
    [
        (
            "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
            "mynamespace",
        )
    ],
)
def test_deploy_time_pelorus_payload_success(image_sha, namespace):
    """Valid image_sha and namespace create a DeployTimePelorusPayload."""
    _, test_payload, _, _, _ = _make_payloads()
    payload = DeployTimePelorusPayload(
        **test_payload, image_sha=image_sha, namespace=namespace
    )
    assert payload.get_metric_model_name() == "DeployTimePelorusPayload"


@pytest.mark.parametrize(
    "image_sha,namespace",
    [
        # Test for wrong SHA format
        (
            "sha255:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
            "mynamespace",
        ),
        # Test for too long namespace (64 characters)
        (
            "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
            "a" * 64,
        ),
    ],
)
def test_deploy_time_pelorus_payload_error(image_sha, namespace):
    """Invalid image_sha or namespace are rejected by DeployTimePelorusPayload."""
    _, test_payload, _, _, _ = _make_payloads()
    with pytest.raises(ValidationError):
        DeployTimePelorusPayload(
            **test_payload, image_sha=image_sha, namespace=namespace
        )


@pytest.mark.parametrize("commit_hash_length", [7, 40])
def test_commit_time_pelorus_payload_success(commit_hash_length):
    """Commit hashes of length 7 or 40 are accepted."""
    _, _, test_deploy, _, _ = _make_payloads()
    commit_hash = "a" * commit_hash_length
    payload = CommitTimePelorusPayload(
        **test_deploy,
        commit_hash=commit_hash,
    )
    assert payload.commit_hash == commit_hash
    assert payload.get_metric_model_name() == "CommitTimePelorusPayload"


@pytest.mark.parametrize("commit_hash_length", [6, 8, 10, 39, 41, 123])
def test_commit_time_pelorus_payload_error(commit_hash_length):
    _, _, test_deploy, _, _ = _make_payloads()
    commit_hash = "a" * commit_hash_length
    with pytest.raises(ValidationError) as v_error:
        CommitTimePelorusPayload(
            **test_deploy,
            commit_hash=commit_hash,
        )
    assert "commit_hash" in str(v_error.value)


@pytest.mark.parametrize(
    "metric_spec_key,payload_key",
    [
        ("COMMIT_TIME", "commit"),
        ("COMMIT_TIME_STR", "commit"),
        ("DEPLOY_TIME", "deploy"),
        ("FAILURE", "failure"),
        ("PING", "payload"),
    ],
    ids=["commit_enum", "commit_str", "deploy", "failure", "ping"],
)
def test_pelorus_metric_success(metric_spec_key, payload_key):
    """PelorusMetric accepts valid metric_spec and metric_data combinations."""
    _, test_payload, test_deploy, test_commit, test_failure = _make_payloads()

    payloads = {
        "commit": CommitTimePelorusPayload(**test_commit),
        "deploy": DeployTimePelorusPayload(**test_deploy),
        "failure": FailurePelorusPayload(**test_failure),
        "payload": PelorusPayload(**test_payload),
    }
    specs = {
        "COMMIT_TIME": PelorusMetricSpec.COMMIT_TIME,
        "COMMIT_TIME_STR": "committime",
        "DEPLOY_TIME": PelorusMetricSpec.DEPLOY_TIME,
        "FAILURE": PelorusMetricSpec.FAILURE,
        "PING": PelorusMetricSpec.PING,
    }

    metric_spec = specs[metric_spec_key]
    metric_data = payloads[payload_key]
    metric = PelorusMetric(metric_spec=metric_spec, metric_data=metric_data)
    assert metric.metric_spec == PelorusMetricSpec(metric_spec)
    assert metric.metric_data == metric_data


@pytest.mark.parametrize(
    "metric_spec,use_fake_payload",
    [
        ("spec_name", False),
        (PelorusMetricSpec.COMMIT_TIME, True),
    ],
    ids=["invalid_spec", "non_pelorus_payload"],
)
def test_pelorus_metric_error(metric_spec, use_fake_payload):
    _, _, test_deploy, _, _ = _make_payloads()

    metric_data = (
        FakePelorusPayload(**test_deploy)
        if use_fake_payload
        else DeployTimePelorusPayload(**test_deploy)
    )
    with pytest.raises(ValidationError):
        PelorusMetric(metric_spec=metric_spec, metric_data=metric_data)

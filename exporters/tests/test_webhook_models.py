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

from contextlib import nullcontext
from secrets import choice
from string import ascii_letters

import pytest
from pydantic import BaseModel, ValidationError

from webhook.models.pelorus_webhook import (
    CommitTimePelorusPayload,
    DeployTimePelorusPayload,
    FailurePelorusPayload,
    PelorusMetric,
    PelorusMetricSpec,
    PelorusPayload,
)

# TODO no tests for PelorusDeliveryHeaders

test_payload = {
    "app": "todolist",
    "timestamp": "1678269658",
}
test_deploy = {
    **test_payload,
    "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
    "namespace": "mynamespace",
}
test_commit = {
    **test_deploy,
    "commit_hash": "abc123w",
}
test_failure = {
    **test_payload,
    "failure_id": "test",
    "failure_event": "created",
}


class FakePelorusPayload(BaseModel):
    timestamp: str
    app: str
    image_sha: str
    namespace: str


@pytest.mark.parametrize(
    "app,timestamp",
    [
        (123456, 1678269658),
        ("todolist", "1678269658"),
    ],
)
def test_pelorus_payload_success(app, timestamp):
    """
    Test for the base PelorusPayload class. This class is inherited
    by every other payload classes and contains only two required
    attributes.

    Checks the validations of the app and timestamp fields for various
    conditions.
    """
    payload = PelorusPayload(app=app, timestamp=timestamp)
    assert payload.get_metric_model_name() == "PelorusPayload"


@pytest.mark.parametrize(
    "app,timestamp",
    [
        (123456, 123457890),
        ("todolist", "123456789"),
        ("todolist", "123456789"),
        ("todolist", 12345678901),
        ("todolist", "Mon Mar 6 15:31:32 2023 +0100"),
        ("todolist", 1262307660),
        ("todolist", 2840144462),
    ],
)
def test_pelorus_wrong_timestamp(app, timestamp):
    """
    Test for the wrong timestamp of the PelorusPayload class.
    The timestamp should be a valid EPOCH format, which is
    10 digit number.
    """
    with pytest.raises(ValidationError):
        PelorusPayload(app=app, timestamp=timestamp)


@pytest.mark.parametrize(
    "app,timestamp",
    [
        # Test for too long app name (200 characters limit)
        ("".join(choice(ascii_letters) for _ in range(201)), "timestamp_str"),
        # Test for too long app name (50 characters limit)
        ("todolist", "".join(choice(ascii_letters) for _ in range(51))),
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
    """
    Test for the FailurePelorusPayload class. This class is a subclass of the
    PelorusPayload and includes two additional fields: failure_id and failure_event.

    Checks the validations of the failure_id and failure_event fields.
    """
    # Test for proper event types
    # Ensure class name from get_metric_model_name() matches FailurePelorusPayload
    payload = FailurePelorusPayload(
        **test_payload,
        failure_id=failure_id,
        failure_event=failure_event,
    )
    assert payload.failure_event in ["created", "resolved"]
    assert payload.get_metric_model_name() == "FailurePelorusPayload"


@pytest.mark.parametrize("failure_id,failure_event", [("Issue-1", "Other")])
def test_failure_pelorus_payload_error(failure_id, failure_event):
    # Wrong event type. Only 'created' and 'resolved' events are supported
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
    """
    Test for the DeployTimePelorusPayload class. This class is a subclass of the
    PelorusPayload and includes two additional fields: image_sha and namespace.

    Checks the validations of the image_sha and namespace fields.
    """
    # Test for proper image sha and proper namespace
    # Ensure class name from get_metric_model_name() matches DeployTimePelorusPayload
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
            "".join(choice(ascii_letters) for _ in range(64)),
        ),
    ],
)
def test_deploy_time_pelorus_payload_error(image_sha, namespace):
    """
    Test for the DeployTimePelorusPayload class. This class is a subclass of the
    PelorusPayload and includes two additional fields: image_sha and namespace.

    Checks the validations of the image_sha and namespace fields.
    """
    with pytest.raises(ValidationError):
        DeployTimePelorusPayload(
            **test_payload, image_sha=image_sha, namespace=namespace
        )


@pytest.mark.parametrize("commit_hash_length", [7, 40])
def test_commit_time_pelorus_payload_success(commit_hash_length):
    """
    Test for the CommitTimePelorusPayload class. This class is a subclass of the
    DeployTimePelorusPayload and includes only additional field: commit_hash.

    Checks the validations of the commit_hash field.
    """

    random_commit_hash = "".join(
        choice(ascii_letters) for _ in range(commit_hash_length)
    )
    # Test for proper commit hash
    # Ensure class name from get_metric_model_name() matches DeployTimePelorusPayload
    payload = CommitTimePelorusPayload(
        **test_deploy,
        commit_hash=random_commit_hash,
    )
    assert payload.commit_hash == random_commit_hash
    assert payload.get_metric_model_name() == "CommitTimePelorusPayload"


@pytest.mark.parametrize("commit_hash_length", [6, 8, 10, 39, 41, 123])
def test_commit_time_pelorus_payload_error(commit_hash_length):
    random_commit_hash = "".join(
        choice(ascii_letters) for _ in range(commit_hash_length)
    )
    # Test for wrong commit hash length which must be either 7 o 40 characters
    with pytest.raises(ValidationError):
        CommitTimePelorusPayload(
            **test_deploy,
            commit_hash=random_commit_hash,
        )
    # assert (
    #     "Git SHA-1 hash must be either 7 (short) or 40 (long) characters long"
    #     in str(v_error.value)
    # )


@pytest.mark.parametrize(
    "metric_spec,metric_data",
    [
        (PelorusMetricSpec.COMMIT_TIME, CommitTimePelorusPayload(**test_commit)),
        ("committime", CommitTimePelorusPayload(**test_commit)),
        (PelorusMetricSpec.DEPLOY_TIME, DeployTimePelorusPayload(**test_deploy)),
        (PelorusMetricSpec.FAILURE, FailurePelorusPayload(**test_failure)),
        (PelorusMetricSpec.PING, PelorusPayload(**test_payload)),
    ],
)
def test_pelorus_metric_success(metric_spec, metric_data):
    """
    Test for the PelorusMetric class. This class is used as a return value
    from the plugin function. It consists of the metric specification
    metric_spec and the metric data represented by the metric_data value.

    Checks the validations of the PelorusMetric instance, which should
    accept only proper data types:
        metric_spec must be enum value from the PelorusMetricSpec
        metric_data must be a subclass of the PelorusPayload
    """

    with nullcontext() as context:
        # TODO do we need both?
        # can't we assume the spec from metric_data type?
        # or even from the header?
        PelorusMetric(metric_spec=metric_spec, metric_data=metric_data)

    assert context is None


@pytest.mark.parametrize(
    "metric_spec,metric_data",
    [
        # Ensure the value is an enumeration number from the PelorusMetricSpec
        ("spec_name", DeployTimePelorusPayload(**test_deploy)),
        # Ensure payload is inheriting from PelorusPayload
        (PelorusMetricSpec.COMMIT_TIME, FakePelorusPayload(**test_deploy)),
        # TODO shouldn't the mix match also break?
        # (PelorusMetricSpec.DEPLOY_TIME, FailurePelorusPayload(**test_failure)),
    ],
)
def test_pelorus_metric_error(metric_spec, metric_data):
    with pytest.raises(ValidationError):
        PelorusMetric(metric_spec=metric_spec, metric_data=metric_data)

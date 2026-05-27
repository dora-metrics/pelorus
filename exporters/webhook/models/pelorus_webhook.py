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

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from pelorus.timeutil import METRIC_TIMESTAMP_THRESHOLD_MINUTES, is_out_of_date_timestamp


class PelorusMetricSpec(str, Enum):
    """Webhook event types, one per exporter (committime, deploytime, failure)."""

    COMMIT_TIME = "committime"
    DEPLOY_TIME = "deploytime"
    FAILURE = "failure"
    PING = "ping"


class PelorusDeliveryHeaders(BaseModel):
    """
    Headers expected in Pelorus webhook POST requests.

    Uses ``x-pelorus-event`` to identify the metric type and optionally
    ``x-hub-signature-256`` for HMAC-SHA256 payload verification.
    """

    model_config = {"populate_by_name": True}

    event_type: PelorusMetricSpec = Field(examples=["committime"], alias="x-pelorus-event")

    # This is HMAC-SHA256 represented by 'sha256=' prefix followed by hexadecimal
    # 64 characters (32 bytes x 2 hex digits per byte).
    # Note the "HTTP Message Signatures" specification, however it's draft:
    # https://datatracker.ietf.org/doc/draft-ietf-httpbis-message-signatures/
    x_hub_signature_256: Optional[str] = Field(default=None, alias="x-hub-signature-256")

    @field_validator("x_hub_signature_256", mode="before")
    @classmethod
    def validate_x_hub_signature_256(cls, value):
        if value is not None:
            if "=" not in value:
                raise ValueError(
                    "Signature should be in format 'sha256=' followed by 64 characters"
                )
            algorithm, signature = value.split("=", 1)
            if algorithm != "sha256":
                raise ValueError("Signature should use sha256 algorithm")
            if not signature or len(signature) != 64:
                raise ValueError(
                    "Signature should be in format 'sha256=' followed by 64 characters"
                )
            try:
                int(signature, 16)
            except ValueError:
                raise ValueError(
                    "Signature must contain only hexadecimal characters after 'sha256='"
                ) from None
        return value


def _validate_timestamp_threshold(v: int) -> int:
    if is_out_of_date_timestamp(v):
        raise ValueError(
            f"Timestamp cannot be older than {METRIC_TIMESTAMP_THRESHOLD_MINUTES} minutes"
        )
    return v


class PelorusPayload(BaseModel):
    """
    Base class for the Pelorus payload model that is used across data
    received by different webhooks.

    Attributes:
        app (str): Application name.
        timestamp (int): 10 digit EPOCH timestamp of the event. This
                         is different from the time when the webhook
                         could have been received. The date value must
                         be between 1.1.2010 and 1.1.2060.
    """

    app: str = Field(max_length=200, pattern=r"^[a-zA-Z0-9._/,\-]+$")

    timestamp: int = Field(ge=1262307661, le=2840144461)

    def get_metric_model_name(self) -> str:
        return type(self).__name__


class FailurePelorusPayload(PelorusPayload):
    """
    Failure Pelorus payload model.

    Attributes:
        failure_id (str): failure identified for a given app.
        failure_event (FailureEvent): failure may have only two events
                                      created or resolved states.
    """

    class FailureEvent(str, Enum):
        """
        The failure may be one of two events. When it occurs it's created
        and when it is resolved it's closed. Both events are different
        Prometheus metrics, so we need to distinguish between them.
        """

        CREATED = "created"
        RESOLVED = "resolved"

    # str because issue IDs may mix letters and digits, e.g. "Issue-1"
    failure_id: str = Field(max_length=200, pattern=r"^[a-zA-Z0-9._/,\-]+$")
    failure_event: FailureEvent

    @field_validator("timestamp")
    @classmethod
    def accepted_timestamp_threshold(cls, v):
        return _validate_timestamp_threshold(v)


class DeployTimePelorusPayload(PelorusPayload):
    """
    Deploy time Pelorus payload model, represents the deployment of
    an application.

    Timestamp of the deployment time can not be older than the one defined in the
    METRIC_TIMESTAMP_THRESHOLD_MINUTES.

    Attributes:
        image_sha (str): The container image SHA which was used for the
                         deployment.
        namespace (str): The k8s namespace used for the deployment.
    """

    image_sha: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    # rfc1035/rfc1123: An alphanumeric string, with a maximum length of 63 characters
    namespace: str = Field(max_length=63, pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

    @field_validator("timestamp")
    @classmethod
    def accepted_timestamp_threshold(cls, v):
        return _validate_timestamp_threshold(v)


class CommitTimePelorusPayload(DeployTimePelorusPayload):
    """
    Source code commit time Pelorus payload model, represents the time when
    the change was committed to the codebase and later used to deploy an
    application. It uses the same data as Deploy time, except it adds
    the commit hash to the metric.

    Attributes:
        commit_hash (str): Commit SHA-1 hash associated with the commit
    """

    commit_hash: str = Field()

    @field_validator("commit_hash")
    @classmethod
    def check_git_hash_length(cls, v):
        if len(v) not in (7, 40):
            raise ValueError(
                "Git SHA-1 hash must be either 7 (short) or 40 (long) characters long"
            )
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(
                "Git SHA-1 hash must contain only hexadecimal characters"
            ) from None
        return v

    @field_validator("timestamp")
    @classmethod
    def accepted_timestamp_threshold(cls, v):
        return v


class PelorusMetric(BaseModel):
    """
    Class to be used as return object from each individual Webhook plugin.

    Attributes:
        metric_spec (PelorusMetricSpec): Metric specification type
        metric_data (PelorusPayload): Data that comes from the webhook payload.
    """

    metric_spec: PelorusMetricSpec
    metric_data: PelorusPayload

    @model_validator(mode="before")
    @classmethod
    def check_pelorus_payload_type(cls, data):
        """
        Validate if the metric_data is in fact a subclass of the PelorusPayload.
        Note that TypeVar from typing that bounds to the PelorusPayload class
        is not working as expected and do not raise any ValidationError if improper
        object is passed.
        """
        if isinstance(data, dict):
            v = data.get("metric_data")
        else:
            v = getattr(data, "metric_data", None)
        if v is not None and not isinstance(v, PelorusPayload):
            raise ValueError("metric_data must be a subclass of PelorusPayload")
        return data

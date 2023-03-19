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

from pydantic import BaseModel, Field, validator


class PelorusMetricSpec(str, Enum):
    """
    The metric should correspond to the known exporter types.
    """

    COMMIT_TIME = "committime"
    DEPLOY_TIME = "deploytime"
    FAILURE = "failure"
    PING = "ping"


class PelorusDeliveryHeaders(BaseModel):
    # https://docs.pydantic.dev/usage/models/
    event_type: PelorusMetricSpec = Field(example="committime", alias="x-pelorus-event")


class PelorusPayload(BaseModel):
    """
    Base class for the Pelorus payload model that is used across data
    received by different webhooks.

    Attributes:
        app (str): Application name.
        timestamp (int): 10 digit EPOCH timestamp of the event. This
                         is different from the time when the webhook
                         could have been received. The date value must
                         be between 1.1.2010 and 1.1.2060
    """

    # Even if we consider git project name as app, it still should be below 100
    app: str = Field(max_length=200)

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

    failure_id: str  # It's an str, because issue may be mix of str and int, e.g. Issue-1
    failure_event: FailureEvent


class DeployTimePelorusPayload(PelorusPayload):
    """
    Deploy time Pelorus payload model, represents the deployment of
    an application.

    Attributes:
        image_sha (str): The container image SHA which was used for the
                         deployment.
        namespace (str): The k8s namespace used for the deployment.
    """

    image_sha: str = Field(regex=r"^sha256:[a-f0-9]{64}$")
    # rfc1035/rfc1123: An alphanumeric string, with a maximum length of 63 characters
    namespace: str = Field(max_length=63)


class CommitTimePelorusPayload(DeployTimePelorusPayload):
    """
    Source code commit time Pelorus payload model, represents the time when
    the change was committed to the codebase and later used to deploy an
    application. It uses the same data as Deploy time, except it adds
    the commit hash to the metric.

    Attributes:
        commit_hash (str): Commit SHA-1 hash associated with the commit
    """

    commit_hash: str = Field(min_length=7, max_length=40)

    @validator("commit_hash", check_fields=False)
    def check_git_hash_length(cls, v):
        if len(v) in (7, 40):
            return v
        raise ValueError(
            "Git SHA-1 hash must be either 7 (short) or 40 (long) characters long"
        )


class PelorusMetric(BaseModel):
    """
    Class to be used as return object from each individual Webhook plugin.

    Attributes:
        metric_spec (PelorusMetricSpec): Metric specification type
        metric_data (PelorusPayload): Data that comes from the webhook payload.
    """

    metric_spec: PelorusMetricSpec
    metric_data: PelorusPayload

    @validator("metric_data", pre=True)
    def check_pelorus_payload_type(cls, v):
        """
        Validate if the metric_data is in fact a subclass of the PelorusPayload.
        Note that TypeVar from typing that bounds to the PelorusPayload class
        is not working as expected and do not raise any ValidationError if improper
        object is passed.
        """
        if issubclass(type(v), PelorusPayload):
            return v
        raise TypeError("metric_data must be a subclass of PelorusPayload")

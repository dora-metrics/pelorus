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

import hashlib
import hmac
import http
import json
import logging
from typing import Any, Awaitable, Dict

from pydantic import ValidationError, parse_obj_as
from typing_extensions import override

from webhook.models.pelorus_webhook import (
    CommitTimePelorusPayload,
    DeployTimePelorusPayload,
    FailurePelorusPayload,
    PelorusDeliveryHeaders,
    PelorusMetric,
    PelorusMetricSpec,
)

from .pelorus_handler_base import (
    Headers,
    HTTPException,
    PelorusWebhookPlugin,
    PelorusWebhookResponse,
)


def _verify_payload_signature(
    secret: bytes, signature_secret: str, json_payload_data: Dict[str, str]
) -> bool:
    """
    This function attempts to match the hash of a payload to its data,
    with the understanding that the input JSON may be formatted slightly
    differently, such as having different separators or newlines.

    Any change to a single character in the sender's JSON input will
    change its hash signature. Therefore, on the webhook side,
    this function attempts to ignore separators and newline characters
    in order to match the incoming hash using variations of those formats
    that do not affect the payload data.

    To illustrate this point, consider the following variations of
    the same JSON input, which are actually equivalent:

    {"data": "value", "data2": "value2"}
    {"data":"value","data2":"value2"}
    {"data":"value", "data2":"value2"}
    {"data" :"value","data2" :"value2"}
    {"data" :"value", "data2" :"value2"}
    {"data": "value", "data2": "value2"}\n
    {"data":"value","data2":"value2"}\n
    {"data":"value", "data2":"value2"}\n
    {"data" :"value","data2" :"value2"}\n
    {"data" :"value", "data2" :"value2"}\n
    { "data": "value", "data2": "value2" }
    { "data":"value","data2":"value2" }
    { "data":"value", "data2":"value2" }
    { "data" :"value","data2" :"value2" }
    { "data" :"value", "data2" :"value2" }
    { "data": "value", "data2": "value2" }\n
    { "data":"value","data2":"value2" }\n
    { "data":"value", "data2":"value2" }\n
    { "data" :"value","data2" :"value2" }\n
    { "data" :"value", "data2" :"value2" }\n

    Returns:
        bool: True when the matching hash was found, False otherwise
    """

    separator_formats = [
        (", ", ": "),
        (",", ":"),
        (", ", ":"),
        (",", " :"),
        (", ", " :"),
    ]
    additional_transformation = [
        "extra_spaces_no_newline",
        "extra_spaces_newline",
        "no_extra_spaces_no_newline",
        "no_extra_spaces_newline",
    ]

    for separator in separator_formats:
        for transformation in additional_transformation:
            # no_extra_spaces_no_newline - default
            payload_json_string = json.dumps(
                json_payload_data, separators=separator, indent=None
            )
            payload_json_string = payload_json_string.rstrip("\n")

            if transformation == "extra_spaces_no_newline":
                payload_json_string = "{ " + payload_json_string[1:-1] + " }"
            elif transformation == "extra_spaces_newline":
                payload_json_string = "{ " + payload_json_string[1:-1] + " }"
                payload_json_string = payload_json_string + "\n"
            elif transformation == "no_extra_spaces_newline":
                payload_json_string = payload_json_string + "\n"

            encoded_payload = payload_json_string.encode("utf-8")

            sha256_signature = (
                "sha256="
                + hmac.new(secret, encoded_payload, hashlib.sha256).hexdigest()
            )

            # "X-Hub-Signature-256: sha256=<SHA256_VALUE>"
            if hmac.compare_digest(sha256_signature, signature_secret):
                return True
    return False


class PelorusWebhookHandler(PelorusWebhookPlugin):
    """
    Pelorus Webhook Handler plugin.

    This is a Pelorus plugin for the Pelorus Webhook exporter.

    Data (payload) received in the POST must be in the proper json
    format and match exactly the format required by the Pelorus
    specific metric type, otherwise it won't be processed by
    this plugin.

    To use this plugin the Header information sent by the POST
    method needs to use "User-Agent: Pelorus-Webhook/*" and
    define what is the payload requested event type
    "X-Pelorus-Event" supported by this plugin.

    The supported event types are defined in the PelorusMetricSpec
    enumeration.

    POST Header example:
        Content-Type: application/json
        User-Agent: Pelorus-Webhook/test
        X-Pelorus-Event: committime

    POST data example:
        {
            "app": "mongo-todolist",
            "commit_hash": "5379bad65a3f83853a75aabec9e0e43c75fd18fc",
            "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
            "namespace": "mongo-persistent",
            "timestamp": 1557933657
        }
    """

    user_agent_str = "Pelorus-Webhook/"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.payload_headers = None

    def _pelorus_committime(payload) -> CommitTimePelorusPayload:
        return CommitTimePelorusPayload(**payload)

    def _pelorus_failure(payload) -> FailurePelorusPayload:
        return FailurePelorusPayload(**payload)

    def _pelorus_deploytime(payload) -> DeployTimePelorusPayload:
        return DeployTimePelorusPayload(**payload)

    # Mapping between event_type given by the
    # X-Pelorus-Event that is stored in the PelorusDeliveryHeaders
    # and functions for its' relevant pydantic payload models
    #
    # For 'ping' X-Pelorus_event a pong classmethod that raises
    # HTTPException to send 'pong' response is used.
    handler_functions = {
        PelorusMetricSpec.PING: PelorusWebhookResponse.pong,
        PelorusMetricSpec.COMMIT_TIME: _pelorus_committime,
        PelorusMetricSpec.FAILURE: _pelorus_failure,
        PelorusMetricSpec.DEPLOY_TIME: _pelorus_deploytime,
    }

    @override
    async def _handshake(self, headers: Headers) -> Awaitable[bool]:
        """
        Initial handshake implementation called by the plugin's base handler
        method. The headers must match the PelorusDeliveryHeaders model to
        be recognized by pydantic as valid headers, otherwise exception
        is raised to inform user agent about improper headers immediately.

        Returns:
            bool: True when the handshake based on the headers were success

        Raises:
            HTTPException: headers were improper - validated by pydantic
                           handler were configured with signature, but no
                           signature was found in the headers.
        """
        try:
            self.payload_headers = parse_obj_as(PelorusDeliveryHeaders, headers)
            if self.secret and not self.payload_headers.x_hub_signature_256:
                raise HTTPException(
                    status_code=http.HTTPStatus.BAD_REQUEST,
                    detail="Non existing signature.",
                )
            return issubclass(type(self.payload_headers), PelorusDeliveryHeaders)
        except ValidationError as ex:
            logging.error(headers)
            logging.error(ex)
            raise HTTPException(
                status_code=http.HTTPStatus.BAD_REQUEST,
                detail="Improper headers.",
            )

    @override
    async def _receive_pelorus_payload(
        self, json_payload_data: Any
    ) -> Awaitable[PelorusMetric]:
        """
        Receive payload from the json_payload_data and converts it to the
        proper PelorusMetric by using mapping from the handler_functions.


        Returns:
            Awaitable[PelorusMetric]: with the proper Pelorus payload data.

        Raises:
            HTTPException: If the json_payload was not in a format required
                           by the handler function requested for that payload
                           in the header's 'X-Pelorus_event' event_type.
        """
        if self.payload_headers and self.payload_headers.event_type:
            try:
                if self.secret:
                    if not _verify_payload_signature(
                        self.secret.encode("utf-8"),
                        self.payload_headers.x_hub_signature_256,
                        json_payload_data,
                    ):
                        raise HTTPException(
                            status_code=http.HTTPStatus.BAD_REQUEST,
                            detail="Invalid signature.",
                        )

                data = self.handler_functions[self.payload_headers.event_type](
                    json_payload_data
                )
                return PelorusMetric(
                    metric_spec=self.payload_headers.event_type, metric_data=data
                )
            except ValidationError as ex:
                logging.error(self.payload_headers)
                logging.error(json_payload_data)
                logging.error(ex)
                raise HTTPException(
                    status_code=http.HTTPStatus.UNPROCESSABLE_ENTITY,
                    detail="Invalid payload.",
                )

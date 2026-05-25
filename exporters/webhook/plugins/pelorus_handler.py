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
from typing import Any, Optional

from pydantic import TypeAdapter, ValidationError

try:
    from typing import override
except ImportError:
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

_HEADERS_ADAPTER = TypeAdapter(PelorusDeliveryHeaders)

_SEPARATOR_FORMATS = [
    (", ", ": "),
    (",", ":"),
    (", ", ":"),
    (",", " :"),
    (", ", " :"),
]


def _verify_payload_signature(
    secret: bytes, signature_secret: str, json_payload_data: dict[str, str],
    raw_body: Optional[bytes] = None,
) -> bool:
    """Verify HMAC-SHA256 signature against the raw body first, then
    fall back to re-serialized JSON variants (different separators/whitespace)
    to tolerate formatting differences between sender and receiver."""

    # Fast path: verify against raw request body (standard webhook pattern).
    # This avoids re-serializing JSON in multiple formats when the sender
    # signed the raw HTTP body, which is the common case.
    if raw_body is not None:
        sha256_signature = (
            "sha256="
            + hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
        )
        if hmac.compare_digest(sha256_signature, signature_secret):
            return True

    # Fallback: try re-serialized JSON variants for senders that sign
    # a differently-formatted JSON string than what they transmit.
    for separator in _SEPARATOR_FORMATS:
        base_json = json.dumps(
            json_payload_data, separators=separator, indent=None
        ).rstrip("\n")

        extra_spaces = "{ " + base_json[1:-1] + " }"
        variants = (
            base_json,                  # no_extra_spaces_no_newline
            base_json + "\n",           # no_extra_spaces_newline
            extra_spaces,               # extra_spaces_no_newline
            extra_spaces + "\n",        # extra_spaces_newline
        )

        for payload_json_string in variants:
            sha256_signature = (
                "sha256="
                + hmac.new(
                    secret,
                    payload_json_string.encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()
            )

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

    @staticmethod
    def _pelorus_committime(payload) -> CommitTimePelorusPayload:
        return CommitTimePelorusPayload(**payload)

    @staticmethod
    def _pelorus_failure(payload) -> FailurePelorusPayload:
        return FailurePelorusPayload(**payload)

    @staticmethod
    def _pelorus_deploytime(payload) -> DeployTimePelorusPayload:
        return DeployTimePelorusPayload(**payload)

    # Mapping between event_type given by the
    # X-Pelorus-Event that is stored in the PelorusDeliveryHeaders
    # and functions for its relevant pydantic payload models.
    #
    # For 'ping' X-Pelorus-Event a pong classmethod that raises
    # HTTPException to send 'pong' response is used.
    handler_functions = {
        PelorusMetricSpec.PING: PelorusWebhookResponse.pong,
        PelorusMetricSpec.COMMIT_TIME: _pelorus_committime,
        PelorusMetricSpec.FAILURE: _pelorus_failure,
        PelorusMetricSpec.DEPLOY_TIME: _pelorus_deploytime,
    }

    @override
    async def _handshake(self, headers: Headers) -> bool:
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
            self.payload_headers = _HEADERS_ADAPTER.validate_python(dict(headers))
            if self.secret and not self.payload_headers.x_hub_signature_256:
                raise HTTPException(
                    status_code=http.HTTPStatus.UNAUTHORIZED,
                    detail="Non existing signature.",
                )
            return isinstance(self.payload_headers, PelorusDeliveryHeaders)
        except ValidationError as ex:
            sensitive = ("x-hub-signature-256", "authorization")
            safe_headers = {
                k: v for k, v in dict(headers).items()
                if k.lower() not in sensitive
            }
            logging.error(
                "Handshake failed: invalid headers: %s", safe_headers,
            )
            raise HTTPException(
                status_code=http.HTTPStatus.BAD_REQUEST,
                detail="Improper headers.",
            )

    @override
    async def _receive_pelorus_payload(
        self, json_payload_data: Any
    ) -> PelorusMetric:
        """
        Receive payload from the json_payload_data and converts it to the
        proper PelorusMetric by using mapping from the handler_functions.

        Returns:
            PelorusMetric: with the proper Pelorus payload data.

        Raises:
            HTTPException: If the json_payload was not in a format required
                           by the handler function requested for that payload
                           in the header's 'X-Pelorus-Event' event_type.
        """
        if not self.payload_headers or not self.payload_headers.event_type:
            raise HTTPException(
                status_code=http.HTTPStatus.BAD_REQUEST,
                detail="Missing or invalid event type header.",
            )

        try:
            if self.secret:
                raw_body = await self.request.body()
                if not _verify_payload_signature(
                    self.secret.encode("utf-8"),
                    self.payload_headers.x_hub_signature_256,
                    json_payload_data,
                    raw_body=raw_body,
                ):
                    logging.warning(
                        "HMAC signature verification failed for event %s",
                        self.payload_headers.event_type,
                    )
                    raise HTTPException(
                        status_code=http.HTTPStatus.UNAUTHORIZED,
                        detail="Invalid signature.",
                    )

            handler_fn = self.handler_functions.get(self.payload_headers.event_type)
            if handler_fn is None:
                raise HTTPException(
                    status_code=http.HTTPStatus.UNPROCESSABLE_ENTITY,
                    detail=f"Unsupported event type: {self.payload_headers.event_type}",
                )

            data = handler_fn(json_payload_data)
            return PelorusMetric(
                metric_spec=self.payload_headers.event_type, metric_data=data
            )
        except ValidationError as ex:
            logging.error(
                "Payload validation failed for event %s",
                self.payload_headers.event_type,
            )
            raise HTTPException(
                status_code=http.HTTPStatus.UNPROCESSABLE_ENTITY,
                detail="Invalid payload format.",
            )

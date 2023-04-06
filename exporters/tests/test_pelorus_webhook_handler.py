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
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import parse_obj_as

from webhook.models.pelorus_webhook import (
    CommitTimePelorusPayload,
    DeployTimePelorusPayload,
    FailurePelorusPayload,
    PelorusDeliveryHeaders,
    PelorusMetric,
    PelorusMetricSpec,
    PelorusPayload,
)
from webhook.plugins.pelorus_handler import (
    PelorusWebhookHandler,
    _verify_payload_signature,
)
from webhook.plugins.pelorus_handler_base import Headers, HTTPException


@pytest.mark.asyncio
async def test_pelorus_payload_ping_function():
    """
    Test for the ping-pong functionality.
    The 'ping' event is a special case where the HTTPException
    should be raised with the "pong" response. No payload data
    is required in such case.
    """
    event_type = "ping"
    with pytest.raises(HTTPException) as http_exception:
        PelorusWebhookHandler.handler_functions.get(event_type, lambda payload: None)(
            None
        )
    assert http_exception.value.detail == "pong"
    assert http_exception.value.status_code == http.HTTPStatus.OK


@pytest.mark.parametrize(
    "event_type,json_payload",
    [
        (
            "committime",
            """{
            "app": "mongo-todolist",
            "commit_hash": "5379bad65a3f83853a75aabec9e0e43c75fd18fc",
            "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
            "namespace": "mongo-persistent",
            "timestamp": "1557933657"
        }""",
        ),
        (
            "failure",
            """{
            "app": "todolist",
            "failure_id": "Issue-1",
            "failure_event": "created",
            "timestamp": "1557933657"
        }""",
        ),
        (
            "deploytime",
            """{
            "app": "todolist",
            "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
            "namespace": "mongo-persistent",
            "timestamp": "1557933657"
        }""",
        ),
    ],
)
@pytest.mark.asyncio
async def test_pelorus_payload_functions(event_type, json_payload):
    """
    A positive test if the Pelorus WebHook plugin properly handles
    data payload in the json format which will be coming in via POST
    methods.

    The data payload is associated with the even type that comes
    from the Header of the POST request.
    """
    # We need to use patch as it's async call
    with patch(
        "webhook.plugins.pelorus_handler_base.Request.json",
        new_callable=AsyncMock,
    ) as mock_receive:
        mock_receive.return_value = json.loads(json_payload)
        mock_request = AsyncMock()
        mock_request.json = mock_receive

        json_payload_data = await mock_request.json()

        # Handler function for the event_type
        # Passing json_payload_data to it
        data = PelorusWebhookHandler.handler_functions.get(
            event_type, lambda payload: None
        )(json_payload_data)

        # Compare the received payload data from the handler
        # with the expected data model for the given event type.
        if event_type == PelorusMetricSpec.COMMIT_TIME:
            data_model = parse_obj_as(CommitTimePelorusPayload, json_payload_data)
        elif event_type == PelorusMetricSpec.FAILURE:
            data_model = parse_obj_as(FailurePelorusPayload, json_payload_data)
        elif event_type == PelorusMetricSpec.DEPLOY_TIME:
            data_model = parse_obj_as(DeployTimePelorusPayload, json_payload_data)

        assert data == data_model


@pytest.mark.parametrize(
    "header",
    [
        {"Content-Type": "application/json", "X-Pelorus-Event": "committime"},
        {"Content-Type": "application/json", "X-Pelorus-Event": "deploytime"},
        {"Content-Type": "application/json", "X-Pelorus-Event": "failure"},
        {"Content-Type": "application/json", "X-Pelorus-Event": "ping"},
    ],
)
@pytest.mark.asyncio
async def test_handshake(header):
    """
    Verifies all currently supported X-Pelorus-Event types and ensures
    the handshake returns True for those events.
    """
    headers = Headers(header)
    handler = PelorusWebhookHandler(None, request=None)
    handshake_result = await handler._handshake(headers)
    assert handshake_result


@pytest.mark.parametrize(
    "header",
    [
        {"Content-Type": "application/json", "Other-Event": "ping"},
        {"Content-Type": "application/json", "X-Pelorus-Event": "unsupported"},
    ],
)
@pytest.mark.asyncio
async def test_failed_handshake(header):
    """
    For missing "X-Pelorus-Event" value in the header or other then
    supported event type an HTTPException exception is tested.
    """
    headers = Headers(header)
    handler = PelorusWebhookHandler(None, request=None)
    with pytest.raises(HTTPException) as http_exception:
        await handler._handshake(headers)
    assert http_exception.value.detail == "Improper headers."
    assert http_exception.value.status_code == http.HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize(
    "headers,json_payload",
    [
        (
            {"Content-Type": "application/json", "X-Pelorus-Event": "committime"},
            """{
            "app": "mongo-todolist",
            "commit_hash": "5379bad65a3f83853a75aabec9e0e43c75fd18fc",
            "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
            "namespace": "mongo-persistent",
            "timestamp": "1557933657"
            }""",
        ),
        (
            {"Content-Type": "application/json", "X-Pelorus-Event": "failure"},
            """{
            "app": "todolist",
            "failure_id": "Issue-1",
            "failure_event": "created",
            "timestamp": "1557933657"
            }""",
        ),
        (
            {"Content-Type": "application/json", "X-Pelorus-Event": "deploytime"},
            """{
            "app": "todolist",
            "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
            "namespace": "mongo-persistent",
            "timestamp": "1557933657"
            }""",
        ),
    ],
)
@pytest.mark.asyncio
async def test_pelorus_receive_pelorus_payload_success(headers, json_payload):
    """
    Verifies if the json payload generates proper PelorusMetric as well if the
    improper payload raises proper HTTPException.
    """
    handler_headers = Headers(headers)
    json_payload_data = json.loads(json_payload)
    handler = PelorusWebhookHandler(None, request=None)
    handler.payload_headers = parse_obj_as(PelorusDeliveryHeaders, handler_headers)
    pelorus_metric = await handler._receive_pelorus_payload(json_payload_data)

    assert issubclass(type(pelorus_metric), PelorusMetric)
    assert pelorus_metric.metric_spec == handler.payload_headers.event_type
    assert issubclass(type(pelorus_metric.metric_data), PelorusPayload)


@pytest.mark.parametrize(
    "headers,json_payload",
    [
        (
            {"Content-Type": "application/json", "X-Pelorus-Event": "deploytime"},
            """{
            "wrong_payload": "1557933657"
            }""",
        ),
        (
            {"Content-Type": "application/json", "X-Pelorus-Event": "deploytime"},
            """{
            "app": "mongo-todolist",
            "timestamp": "1557933657"
            }""",
        ),
    ],
)
@pytest.mark.asyncio
async def test_pelorus_receive_pelorus_payload_error(headers, json_payload):
    handler_headers = Headers(headers)
    json_payload_data = json.loads(json_payload)
    handler = PelorusWebhookHandler(None, request=None)
    handler.payload_headers = parse_obj_as(PelorusDeliveryHeaders, handler_headers)
    with pytest.raises(HTTPException) as http_exception:
        await handler._receive_pelorus_payload(json_payload_data)
    assert http_exception.value.detail == "Invalid payload."
    assert http_exception.value.status_code == http.HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    "json_payload_data_bytes",
    [
        b'{"data": "value", "data2": "value2"}',
        b'{"data":"value","data2":"value2"}',
        b'{"data":"value", "data2":"value2"}',
        b'{"data" :"value","data2" :"value2"}',
        b'{"data" :"value", "data2" :"value2"}',
        b'{ "data": "value", "data2": "value2" }',
        b'{ "data":"value","data2":"value2" }',
        b'{ "data":"value", "data2":"value2" }',
        b'{ "data" :"value","data2" :"value2" }',
        b'{ "data" :"value", "data2" :"value2" }',
        b'{"data": "value", "data2": "value2"}\n',
        b'{"data":"value","data2":"value2"}\n',
        b'{"data":"value", "data2":"value2"}\n',
        b'{"data" :"value","data2" :"value2"}\n',
        b'{"data" :"value", "data2" :"value2"}\n',
        b'{ "data": "value", "data2": "value2" }\n',
        b'{ "data":"value","data2":"value2" }\n',
        b'{ "data":"value", "data2":"value2" }\n',
        b'{ "data" :"value","data2" :"value2" }\n',
        b'{ "data" :"value", "data2" :"value2" }\n',
    ],
)
def test_verify_payload_signature_different_json(json_payload_data_bytes):
    """
    Verifies if the json payload was properly verified based on provided json string.

    Even if the string of the payload format is different we should still find a match as the
    format does not really affect it's content.
    """
    json_payload_data = {"data": "value", "data2": "value2"}
    secret = b"My Secret"
    calculated_hash = (
        "sha256="
        + hmac.new(secret, json_payload_data_bytes, hashlib.sha256).hexdigest()
    )

    assert _verify_payload_signature(secret, calculated_hash, json_payload_data) is True


@pytest.mark.parametrize(
    "secret,expected_signature,json_payload_data",
    [
        (
            b"MySecret",
            "sha256=f1dbf8a5d2aa74fb479c6bab52d80e947c66c98c131bb2fcfe97a6912623b05d",
            {"data": "value", "data2": "value2"},
        ),
    ],
)
def test_verify_payload_not_matching_hash(
    secret, expected_signature, json_payload_data
):
    assert (
        _verify_payload_signature(secret, expected_signature, json_payload_data)
        is False
    )

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
import time

import pytest
from pydantic import TypeAdapter

from webhook.models.pelorus_webhook import (
    CommitTimePelorusPayload,
    DeployTimePelorusPayload,
    FailurePelorusPayload,
    PelorusDeliveryHeaders,
    PelorusMetric,
    PelorusPayload,
)
from webhook.plugins.pelorus_handler import (
    PelorusWebhookHandler,
    _verify_payload_signature,
)
from webhook.plugins.pelorus_handler_base import Headers, HTTPException

def _current_timestamp():
    return int(time.time())


@pytest.mark.asyncio
async def test_pelorus_payload_ping_function():
    """Verify 'ping' event raises HTTPException with 'pong' response."""
    event_type = "ping"
    handler = PelorusWebhookHandler.handler_functions[event_type]
    with pytest.raises(HTTPException) as http_exception:
        handler(None)
    assert http_exception.value.detail == "pong"
    assert http_exception.value.status_code == http.HTTPStatus.OK


@pytest.mark.parametrize(
    "event_type,json_payload,expected_model",
    [
        (
            "committime",
            """{
            "app": "mongo-todolist",
            "commit_hash": "5379bad65a3f83853a75aabec9e0e43c75fd18fc",
            "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
            "namespace": "mongo-persistent"
            }""",
            CommitTimePelorusPayload,
        ),
        (
            "failure",
            """{
            "app": "todolist",
            "failure_id": "Issue-1",
            "failure_event": "created"
            }""",
            FailurePelorusPayload,
        ),
        (
            "deploytime",
            """{
            "app": "todolist",
            "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
            "namespace": "mongo-persistent"
            }""",
            DeployTimePelorusPayload,
        ),
    ],
)
@pytest.mark.asyncio
async def test_pelorus_payload_functions(event_type, json_payload, expected_model):
    """Verify handler functions return correct payload models for each event type."""
    json_data = json.loads(json_payload)
    json_data["timestamp"] = _current_timestamp()

    handler = PelorusWebhookHandler.handler_functions[event_type]
    data = handler(json_data)

    data_model = TypeAdapter(expected_model).validate_python(json_data)
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
    """Missing or unsupported X-Pelorus-Event raises HTTPException."""
    headers = Headers(header)
    handler = PelorusWebhookHandler(None, request=None)
    with pytest.raises(HTTPException) as http_exception:
        await handler._handshake(headers)
    assert http_exception.value.detail == "Invalid headers."
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
            "namespace": "mongo-persistent"
            }""",
        ),
        (
            {"Content-Type": "application/json", "X-Pelorus-Event": "failure"},
            """{
            "app": "todolist",
            "failure_id": "Issue-1",
            "failure_event": "created"
            }""",
        ),
        (
            {"Content-Type": "application/json", "X-Pelorus-Event": "deploytime"},
            """{
            "app": "todolist",
            "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
            "namespace": "mongo-persistent"
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
    json_payload_data["timestamp"] = _current_timestamp()
    handler = PelorusWebhookHandler(None, request=None)
    handler.payload_headers = TypeAdapter(PelorusDeliveryHeaders).validate_python(dict(handler_headers))
    pelorus_metric = await handler._receive_pelorus_payload(json_payload_data)

    assert isinstance(pelorus_metric, PelorusMetric)
    assert pelorus_metric.metric_spec == handler.payload_headers.event_type
    assert isinstance(pelorus_metric.metric_data, PelorusPayload)


@pytest.mark.parametrize(
    "headers,json_payload",
    [
        (
            {"Content-Type": "application/json", "X-Pelorus-Event": "deploytime"},
            """{
            "wrong_payload": "1557933657"
            }""",
        ),
    ],
)
@pytest.mark.asyncio
async def test_pelorus_receive_pelorus_payload_error(headers, json_payload):
    handler_headers = Headers(headers)
    json_payload_data = json.loads(json_payload)
    handler = PelorusWebhookHandler(None, request=None)
    handler.payload_headers = TypeAdapter(PelorusDeliveryHeaders).validate_python(dict(handler_headers))
    with pytest.raises(HTTPException) as http_exception:
        await handler._receive_pelorus_payload(json_payload_data)
    assert "Invalid payload" in http_exception.value.detail
    assert http_exception.value.status_code == http.HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    "headers,json_payload",
    [
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
async def test_pelorus_receive_pelorus_payload_timestamp_too_old(headers, json_payload):
    handler_headers = Headers(headers)
    json_payload_data = json.loads(json_payload)
    handler = PelorusWebhookHandler(None, request=None)
    handler.payload_headers = TypeAdapter(PelorusDeliveryHeaders).validate_python(dict(handler_headers))
    with pytest.raises(HTTPException) as http_exception:
        await handler._receive_pelorus_payload(json_payload_data)
    assert "Invalid payload" in http_exception.value.detail
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
    """Signature verification succeeds regardless of JSON whitespace formatting."""
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

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

import http
import json
import time
from typing import Any, Awaitable
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import ValidationError, parse_obj_as
from typing_extensions import override

from webhook.models.pelorus_webhook import (
    CommitTimePelorusPayload,
    PelorusMetric,
    PelorusMetricSpec,
)
from webhook.plugins.pelorus_handler_base import (
    Headers,
    HTTPException,
    PelorusWebhookPlugin,
    PelorusWebhookResponse,
    Request,
)


@pytest.mark.parametrize(
    "http_response,http_response_code",
    [("Invalid Payload.", 422), ("Invalid Payload.", "422")],
)
def test_pelorus_webhook_valid_response(http_response, http_response_code):
    """
    Test for the PelorusWebhookResponse class. The response code is a valid
    HTTPStatus code. The http_response is valid string, so the
    PelorusWebhookResponse is also valid.
    """

    # Test for proper message and response code is used.
    response = PelorusWebhookResponse(
        http_response=http_response, http_response_code=http_response_code
    )

    assert response.http_response == http_response
    assert response.http_response_code == http.HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    "http_response,http_response_code",
    [
        (None, http.HTTPStatus.UNPROCESSABLE_ENTITY),
        ("Invalid Payload.", 99),
        ("Invalid Payload.", 601),
        ("Invalid Payload.", None),
    ],
)
def test_pelorus_webhook_invalid_response(http_response, http_response_code):
    """
    Negative test for the PelorusWebhookResponse class.
    The response code must be a valid and http_response must be valid string.
    """
    with pytest.raises(ValidationError):
        PelorusWebhookResponse(
            http_response=http_response, http_response_code=http_response_code
        )


def test_pelorus_webhook_pong_response():
    """
    Test for the proper "pong" response which can be used by
    any implemented plugin.
    """

    with pytest.raises(HTTPException) as http_exception:
        PelorusWebhookResponse.pong(None)

    assert type(http_exception).__name__ == "ExceptionInfo"
    assert http_exception.typename == "HTTPException"

    assert http_exception.value.detail == "pong"
    assert http_exception.value.status_code == http.HTTPStatus.OK


def test_abstract_classes():
    """
    Test for the plugin that did not implement required abstract methods.
    """

    class MyPelorusWebhookPlugin(PelorusWebhookPlugin):
        def __init__(self, handshake_headers: Headers, request: Request) -> None:
            super().__init__(handshake_headers, request)

    # We should get an error:
    # TypeError: Can't instantiate abstract class MyPelorusWebhookPlugin with abstract
    #            methods _receive_pelorus_payload, handshake
    with pytest.raises(TypeError) as type_error:
        MyPelorusWebhookPlugin(None, None)

    assert (
        str(type_error.value)
        == "Can't instantiate abstract class MyPelorusWebhookPlugin "
        + "with abstract methods _handshake, _receive_pelorus_payload"
    )


class SimplePelorusWebhookPlugin(PelorusWebhookPlugin):
    @override
    async def _handshake(self) -> Awaitable[bool]:
        pass

    @override
    async def _receive_pelorus_payload(self, Any) -> Awaitable[PelorusMetric]:
        pass


@pytest.mark.parametrize(
    "handshake_headers,request_data",
    [
        ("Header.", "request data"),
    ],
)
def test_pelorus_webhook_plugin_abc(handshake_headers, request_data):
    """
    Test for the plugin that did implement required abstract methods.
    """

    plugin_instance = SimplePelorusWebhookPlugin(
        handshake_headers=handshake_headers, request=request_data
    )

    assert plugin_instance.headers == handshake_headers
    assert plugin_instance.request == request_data


class WithUserAgentWebhookPlugin(PelorusWebhookPlugin):
    user_agent_str = "Pelorus-Webhook/"


class WithoutUserAgentWebhookPlugin(PelorusWebhookPlugin):
    pass


class EmptyUserAgentWebhookPlugin(PelorusWebhookPlugin):
    user_agent_str = ""


def test_check_can_handle_methods():
    """
    Tests if the plugin can handle data based on the provided
    string information that normally is given by the
    "User-Agent:" header information.

    Pelorus Webhook loads many plugins so each plugin should
    know what payload data can it handle.
    """

    # user_agent_str set to "Pelorus-Webhook/"
    assert WithUserAgentWebhookPlugin.can_handle("Pelorus-Webhook/")
    assert WithUserAgentWebhookPlugin.can_handle("Pelorus-Webhook/suffix")
    assert not WithUserAgentWebhookPlugin.can_handle("")
    assert not WithUserAgentWebhookPlugin.can_handle(None)
    assert not WithUserAgentWebhookPlugin.can_handle("Incompatible-Webhook")

    # user_agent_str not defined
    assert not WithoutUserAgentWebhookPlugin.can_handle(None)
    assert not WithoutUserAgentWebhookPlugin.can_handle("")


def test_plugin_register_methods():
    """
    Test if the register() method of the plugin
    properly returns the identifier of the plugin.

    The plugin identifier is a lower case string
    from the user_agent_str value of the plugin.
    """

    assert (
        WithUserAgentWebhookPlugin.register()
        == WithUserAgentWebhookPlugin.user_agent_str.lower()
    )

    with pytest.raises(NotImplementedError):
        WithoutUserAgentWebhookPlugin.register()

    with pytest.raises(NotImplementedError):
        EmptyUserAgentWebhookPlugin.register()


def test_check_is_pelorus_webhook_handler():
    """
    Test if the plugin is a proper Pelorus handler.
    """

    assert WithUserAgentWebhookPlugin.is_pelorus_webhook_handler()


def test_check_is_pelorus_not_webhook_handler():
    """
    Test if the plugin is not a proper Pelorus handler.
    """

    assert not WithoutUserAgentWebhookPlugin.is_pelorus_webhook_handler()


class UserAgentWebhookPlugin(PelorusWebhookPlugin):
    @override
    async def _handshake(self, headers: Headers) -> Awaitable[bool]:
        time.sleep(0.1)
        return True

    @override
    async def _receive_pelorus_payload(
        self, json_payload_data: Any
    ) -> Awaitable[PelorusMetric]:
        time.sleep(0.1)
        pelorus_data = parse_obj_as(CommitTimePelorusPayload, json_payload_data)
        metric = PelorusMetric(
            metric_spec=PelorusMetricSpec.COMMIT_TIME, metric_data=pelorus_data
        )
        return metric


@pytest.mark.asyncio
async def test_receive_invalid_payload():
    """
    Test if the improper json payload data from the
    webhook's request normally received from the POST
    properly raises HTTPException.
    """

    with patch(
        "webhook.plugins.pelorus_handler_base.Request.json",
        new_callable=AsyncMock,
    ) as mock_receive:
        mock_receive.side_effect = json.JSONDecodeError("Test Error", "{}", 0)
        mock_request = Mock()
        mock_request.json = mock_receive

        plugin = UserAgentWebhookPlugin(None, request=mock_request)
        with pytest.raises(HTTPException) as http_error:
            await plugin._receive()
        assert http_error.value.status_code == http.HTTPStatus.BAD_REQUEST
        assert http_error.value.detail == "Invalid payload format."


@pytest.mark.asyncio
async def test_receive_valid_payload():
    """
    Test if the _receive method properly returns
    the json payload data.
    """

    with patch(
        "webhook.plugins.pelorus_handler_base.Request.json",
        new_callable=AsyncMock,
    ) as mock_receive:
        json_payload = '{"app": "todolist", "commit_hash": "5379bad65a3f83853a75aabec9e0e43c75fd18fc"}'
        mock_receive.return_value = json.loads(json_payload)
        mock_request = Mock()
        mock_request.json = mock_receive

        # Test if the json was properly received from the request
        plugin = UserAgentWebhookPlugin(
            handshake_headers="headers", request=mock_request
        )
        result = await plugin._receive()
        assert result == json.loads(json_payload)


@pytest.mark.asyncio
async def test_handshake():
    """
    Test if the handshake() method from the plugin returns
    proper value.
    """
    pelorus_plugin = UserAgentWebhookPlugin(None, None)
    result = await pelorus_plugin.handshake()
    assert result


@pytest.mark.parametrize(
    "json_payload",
    [
        """{
            "app": "mongo-todolist",
            "commit_hash": "5379bad65a3f83853a75aabec9e0e43c75fd18fc",
            "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
            "namespace": "mongo-persistent",
            "timestamp": "1557933657"
        }""",
    ],
)
@pytest.mark.asyncio
async def test_proper_receive_metric(json_payload):
    """
    Test if the receive() wrapper method that calls
    plugin's _receive() method returns proper
    PelorusMetric data.
    """

    with patch(
        "webhook.plugins.pelorus_handler_base.PelorusWebhookPlugin._receive",
        new_callable=AsyncMock,
    ) as mock_receive:
        mock_receive.return_value = json.loads(json_payload)
        plugin = UserAgentWebhookPlugin(None, request=None)
        metric_data = await plugin.receive()
        assert issubclass(type(metric_data), PelorusMetric)


@pytest.mark.asyncio
async def test_improper_receive_metric():
    """
    Test case for the receive() wrapper method that calls
    plugin's _receive() method in which data from the plugin
    is not a proper PelorusMetric type.
    In such case it raises TypeError.
    """

    with patch(
        "webhook.plugins.pelorus_handler_base.PelorusWebhookPlugin._receive",
        new_callable=AsyncMock,
    ) as mock_receive:
        # A simple string instead of PelorusMetric
        mock_receive.return_value = "simple string"
        plugin = SimplePelorusWebhookPlugin(None, None)
        with pytest.raises(TypeError) as type_error:
            await plugin.receive()
        assert str(type_error.value) == "Webhook must be a subclass of PelorusMetric"

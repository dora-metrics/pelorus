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
from abc import ABC, abstractmethod
from json import JSONDecodeError
from typing import Any, Awaitable, Optional

from fastapi import HTTPException as FastapiHTTPException
from pydantic import BaseModel
from starlette.datastructures import Headers as StarletteHeaders
from starlette.requests import Request as StarletteRequest

from webhook.models.pelorus_webhook import PelorusMetric


class HTTPException(FastapiHTTPException):
    """
    HTTPException class used to ensure plugins can import direct class from the
    Pelorus and not fastapi, even if it's same structure.
    """


class Headers(StarletteHeaders):
    """
    Headers class used to ensure plugins can import direct class from the
    Pelorus and not starlette, even if it's same structure.
    """


class Request(StarletteRequest):
    """
    Request class used to ensure plugins can import direct class from the
    Pelorus and not starlette, even if it's same structure.
    """


# TODO this shouldn't be a model?
class PelorusWebhookResponse(BaseModel):
    """
    Class that represents the response to the user-agent making request.
    """

    http_response: str
    http_response_code: http.HTTPStatus

    @classmethod
    def pong(cls, payload_headers: Any):
        """
        Special case of response which raises "pong" type of message for
        the webhook that sent "ping" request.

        Some webhook services uses this "ping-pong" communication to
        register the webhook on the client side as valid one.

        It raises exception to immediately sent response msg.

        Raises:
            HTTPException: "pong" with valid HTTP Status.
        """
        raise HTTPException(detail="pong", status_code=http.HTTPStatus.OK)


class PelorusWebhookPlugin(ABC):
    """
    Base class for the Pelorus Webhook Plugin

    Plugin must introduce itself by the 'user_agent_str' string
    which needs to match the 'User-Agent:' from the http headers
    and implement the following methods:

      - async _handshake(headers: Headers)
      - async _receive_pelorus_payload(json_payload_data: Any)

    The first method is to return True or False based on the
    initial handshake process with the incoming request. Available
    information about that request is within the self.headers and self.request
    values from the corresponding Headers and Request classes.

    Second method is to return one of the objects based on the PelorusMetric
    classes from the incoming payload, which is in json format.

    Attributes:
        handshake_headers: (Headers): Headers that are received by the webhook.
        request: (Request): The request object associated with the webhook.
    """

    user_agent_str = None

    def __init__(self, handshake_headers: Headers, request: Request) -> None:
        super().__init__()
        self.headers = handshake_headers
        self.request = request
        self.payload_data = None

    @abstractmethod
    async def _handshake(self, headers: Headers) -> Awaitable[bool]:
        raise NotImplementedError  # pragma no cover

    @abstractmethod
    async def _receive_pelorus_payload(
        self, json_payload_data: Any
    ) -> Awaitable[PelorusMetric]:
        raise NotImplementedError  # pragma no cover

    async def handshake(self) -> Awaitable[Optional[bool]]:
        """
        Wrapper method to call plugin's _handshake().

        Returns:
            bool: True if handhsake was success

        Raises:
            HTTPException: If handshake did not succeed
        """
        return await self._handshake(self.headers)

    async def receive(self) -> Awaitable[PelorusMetric]:
        """
        Wrapper method that calls the _receive() method
        which gets the payload data in the json_format
        and passes it to the plugin's _receive_pelorus_payload().

        Returns:
            Awaitable[PelorusMetric]: Pelorus Metric from the plugin

        Raises:
            TypeError: if data was not proper PelorusMetric
        """
        payload_data = await self._receive()
        webhook_data = await self._receive_pelorus_payload(payload_data)
        if not issubclass(type(webhook_data), PelorusMetric):
            raise TypeError("Webhook must be a subclass of PelorusMetric")
        return webhook_data

    async def _receive(self) -> Awaitable[Any]:
        """
        Method to receive json data from the request.

        Returns:
            Awaitable[Any]: json data from the request.

        Raises:
            HTTPException: If data was not proper json format
        """
        try:
            return await self.request.json()
        except JSONDecodeError:
            raise HTTPException(
                status_code=http.HTTPStatus.BAD_REQUEST,
                detail="Invalid payload format.",
            )

    @classmethod
    def register(cls) -> str:
        """
        Method used to register plugin with it's identifier.
        The identifier is the user_agent_str from the plugin's implementation.

        This identifier is used to match with the webhooks' POST "User-Agent:"
        data found in the Header of the POST request.

        Returns:
            str: lower case user agent identifier from the plugin's user_agent_str

        Raises:
            NotImplementedError: If the plugin forgot to implement the user_agent_str
        """
        if not cls.user_agent_str:
            raise NotImplementedError
        return cls.user_agent_str.lower()

    @classmethod
    def can_handle(cls, user_agent: str) -> bool:
        """
        Check if this plugin can handle the provided payload
        (recognized by user_agent).

        Attributes:
            user_agent: (str): Value from the Header's "User-Agent:"

        Returns:
            bool: True if this plugin can handle given user_agent
        """
        if user_agent and cls.user_agent_str:
            if user_agent.lower().startswith(str(cls.user_agent_str).lower()):
                return True
        return False

    @classmethod
    def is_pelorus_webhook_handler(cls) -> bool:
        """
        Used for the type checking only to ensure it's actually supported
        Pelorus Webhook plugin.

        Returns:
            bool: True if it's recognized Pelorus Webhook Plugin, False otherwise
        """
        return hasattr(cls, "user_agent_str") and cls.user_agent_str is not None

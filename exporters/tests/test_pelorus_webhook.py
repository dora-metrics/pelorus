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


import json
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from webhook.app import app, load_plugins, register_plugin
from webhook.plugins.pelorus_handler_base import PelorusWebhookPlugin

client = TestClient(app)

TEST_DATA_DIR = Path(__file__).resolve().parent / "data"


@pytest.fixture
def webhook_data_payload(post_request_json_file):
    with open(TEST_DATA_DIR / post_request_json_file) as f:
        data = json.load(f)
    return data


headers_data = {
    "Content-Type": "application/json",
    "User-Agent": "Pelorus-Webhook/test",
}


@pytest.mark.parametrize("post_request_json_file", ["webhook_pelorus_committime.json"])
def test_pelorus_webhook_no_headers(webhook_data_payload):
    """
    There were no headers passed to the request, so the
    preconditions to establish communication should fail.
    """

    webhook_response = client.post("/pelorus/webhook", json=webhook_data_payload)

    assert webhook_response.status_code == HTTPStatus.PRECONDITION_FAILED
    assert webhook_response.text == '{"detail":"Unsupported request."}'


@pytest.mark.parametrize(
    "post_request_json_file, event_type",
    [
        ("webhook_pelorus_committime.json", "committime"),
        ("webhook_pelorus_deploytime.json", "deploytime"),
        ("webhook_pelorus_failure_created.json", "failure"),
        ("webhook_pelorus_failure_resolved.json", "failure"),
    ],
)
def test_pelorus_webhook_post_data(webhook_data_payload, event_type):
    """
    Proper post data for different metrics.
    """

    headers_data["X-Pelorus-Event"] = event_type

    load_plugins()

    webhook_response = client.post(
        "/pelorus/webhook",
        json=webhook_data_payload,
        headers=headers_data,
    )

    assert webhook_response.status_code == HTTPStatus.ACCEPTED
    assert (
        webhook_response.text
        == '{"http_response":"Webhook Received","http_response_code":200}'
    )


@pytest.mark.parametrize("post_request_json_file", ["webhook_pelorus_committime.json"])
def test_pelorus_webhook_too_large_payload(webhook_data_payload):
    """
    Check for the case where payload is too large.
    """

    webhook_data_payload["data"] = "some payload" * 10000

    webhook_response = client.post("/pelorus/webhook", json=webhook_data_payload)

    assert webhook_response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert webhook_response.text == '{"detail":"Content length too big."}'


def test_register_plugin_not_implemented():
    """
    Test that Webhook Plugin which is not fully implemented can't
    be registered
    """
    register_plugin(PelorusWebhookPlugin)


def test_wrong_plugin_dir():
    """
    Test for the non existing plugin folder
    """
    load_plugins("this_directory_is_nonexisting")

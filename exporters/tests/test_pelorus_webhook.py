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
from unittest.mock import patch

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
def test_pelorus_webhook_post_data_no_secret(webhook_data_payload, event_type):
    """
    Proper post data for different metrics.
    No Secret configured.
    """

    headers_data["X-Pelorus-Event"] = event_type

    load_plugins()

    with patch("webhook.app._get_hash_token") as mocked_get_hash:
        mocked_get_hash.return_value = None

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


@pytest.mark.parametrize(
    "post_request_json_file, event_type, hash_signature",
    [
        (
            "webhook_pelorus_committime.json",
            "committime",
            "sha256=1ce994968588a4d69f8732b1cde8c1d3581b38ce7bd97275ed9b0f61a1f2fc78",
        ),
    ],
)
def test_pelorus_webhook_post_data_wrong_x_signature_mismatch(
    webhook_data_payload, event_type, hash_signature
):
    """
    Proper post data for different metrics.
    Secret token is configured and expected to be sent together with the payload.
    SHA256 sent by the sender is in proper format, however wrongly calculated (mismatch)
    """

    headers_data["X-Pelorus-Event"] = event_type
    headers_data["X-Hub-Signature-256"] = hash_signature

    load_plugins()

    with patch("webhook.app._get_hash_token") as mocked_get_hash:
        mocked_get_hash.return_value = "My Secret Token"

        webhook_response = client.post(
            "/pelorus/webhook",
            json=webhook_data_payload,
            headers=headers_data,
        )

        assert webhook_response.status_code == HTTPStatus.BAD_REQUEST
        assert webhook_response.text == '{"detail":"Invalid signature."}'


@pytest.mark.parametrize(
    "post_request_json_file, event_type, hash_signature",
    [
        (
            "webhook_pelorus_committime.json",
            "committime",
            "sha256=1ce994968588a4d69f8732b1cde8c1d3581b38ce7bd97275ed9b0f61a1f2fcxx",
        ),
        (
            "webhook_pelorus_committime.json",
            "committime",
            "bba6199207705f85437a94348b9e4dcc17ee66f81a754ec72c3f36b6808a534f",
        ),
        ("webhook_pelorus_committime.json", "committime", "improper"),
    ],
)
def test_pelorus_webhook_post_data_wrong_x_signature_format(
    webhook_data_payload, event_type, hash_signature
):
    """
    Proper post data for different metrics.
    Secret token is configured and expected to be sent together with the payload.
    SHA256 sent by the sender is in wrong format
    """

    headers_data["X-Pelorus-Event"] = event_type
    headers_data["X-Hub-Signature-256"] = hash_signature

    load_plugins()

    with patch("webhook.app._get_hash_token") as mocked_get_hash:
        mocked_get_hash.return_value = "My Secret Token"

        webhook_response = client.post(
            "/pelorus/webhook",
            json=webhook_data_payload,
            headers=headers_data,
        )

        assert webhook_response.status_code == HTTPStatus.BAD_REQUEST
        assert webhook_response.text == '{"detail":"Improper headers."}'


@pytest.mark.parametrize(
    "post_request_json_file, event_type",
    [
        ("webhook_pelorus_committime.json", "committime"),
    ],
)
def test_pelorus_webhook_post_data_missing_x_signature(
    webhook_data_payload, event_type
):
    """
    The webhook configured to share "My Secret Token", however
    sender do not include X-Hub-Signature-256 in the Header of the POST method
    """

    headers_data["X-Pelorus-Event"] = event_type

    load_plugins()

    with patch("webhook.app._get_hash_token") as mocked_get_hash:
        mocked_get_hash.return_value = "My Secret Token"

        webhook_response = client.post(
            "/pelorus/webhook",
            json=webhook_data_payload,
            headers=headers_data,
        )

        assert webhook_response.status_code == HTTPStatus.BAD_REQUEST
        assert webhook_response.text == '{"detail":"Improper headers."}'


@pytest.mark.parametrize(
    "post_request_json_file, event_type, hash_signature",
    [
        (
            "webhook_pelorus_committime.json",
            "committime",
            "sha256=3ce994968588a4d69f8732b1cde8c1d3581b38ce7bd97275ed9b0f61a1f2fc78",
        ),
        (
            "webhook_pelorus_deploytime.json",
            "deploytime",
            "sha256=bba6199207705f85437a94348b9e4dcc17ee66f81a754ec72c3f36b6808a534f",
        ),
        (
            "webhook_pelorus_failure_created.json",
            "failure",
            "sha256=44082cdb4d7b95c11e401d44cec949918b472e9a44becb5b7ee7d2b21a6428f0",
        ),
        (
            "webhook_pelorus_failure_resolved.json",
            "failure",
            "sha256=2b7d9028fef8110ceff83492e35c938f8ac9b7851bc2307d8bd5ba7f3c3c48f9",
        ),
    ],
)
def test_pelorus_webhook_post_data_x_signature_secret(
    webhook_data_payload, event_type, hash_signature
):
    """
    Proper post data for different metrics.
    Secret token is configured and expected to be sent together with the payload.
    sha256 for the relevant images calculated using (example for webhook_pelorus_failure_resolved):
      $ jq -c "" ./webhook_pelorus_failure_resolved.json | openssl dgst -sha256 -hmac "My Secret Token"
      SHA2-256(stdin)= 2b7d9028fef8110ceff83492e35c938f8ac9b7851bc2307d8bd5ba7f3c3c48f9

    """

    headers_data["X-Pelorus-Event"] = event_type
    headers_data["X-Hub-Signature-256"] = hash_signature

    load_plugins()

    with patch("webhook.app._get_hash_token") as mocked_get_hash:
        mocked_get_hash.return_value = "My Secret Token"

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

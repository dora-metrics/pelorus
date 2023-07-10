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


import subprocess
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from committime.collector_containerimage import (
    SkopeoDataException,
    _cache_container_images_labels,
    get_labels_from_image,
    image_label_cache,
    skopeo_failures,
)

TEST_DATA_DIR = Path(__file__).resolve().parent / "data"


@pytest.fixture
def mock_popen():
    with patch("subprocess.Popen") as mock_popen:
        yield mock_popen


def read_skopeo_fake_data(skopeo_response_json_file):
    with open(TEST_DATA_DIR / skopeo_response_json_file, "rb") as file:
        return file.read()


@pytest.mark.parametrize(
    "returncode, json_file, expected_labels",
    [
        (
            0,
            "skopeo_default_container_labels.json",
            {
                "io.openshift.build.commit.date": "Tue May 16 20:07:52 2023 +0200",
                "io.openshift.build.commit.id": "66f3dc5d6a36afb35e751309207e7c4f137e56b7",
            },
        ),
        (
            0,
            "skopeo_custom_container_labels.json",
            {
                "custom.commit.date": "Tue May 16 20:07:52 2023 +0200",
                "custom.commit.id": "66f3dc5d6a36afb35e751309207e7c4f137e56b7",
            },
        ),
    ],
)
def test_get_labels_from_image(mock_popen, returncode, json_file, expected_labels):
    mocked_process = Mock()
    mocked_process.returncode = returncode
    mocked_process.communicate.return_value = (read_skopeo_fake_data(json_file), b"")
    mock_popen.return_value = mocked_process

    result = get_labels_from_image("sha256_value", "image_uri")

    for key, value in expected_labels.items():
        assert key in result and result[key] == value

    command = "skopeo inspect --cert-dir /var/run/secrets/kubernetes.io/serviceaccount/ image_uri"
    subprocess.Popen.assert_called_once_with(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
    )
    mocked_process.communicate.assert_called_once()

    assert "sha256_value" not in skopeo_failures


@pytest.mark.parametrize(
    "returncode, json_file, missing_labels",
    [
        (
            0,
            "skopeo_missing_container_labels.json",
            ["io.openshift.build.commit.date", "io.openshift.build.commit.id"],
        )
    ],
)
def test_missing_labels_from_image(mock_popen, returncode, json_file, missing_labels):
    mocked_process = Mock()
    mocked_process.returncode = returncode
    mocked_process.communicate.return_value = (read_skopeo_fake_data(json_file), b"")
    mock_popen.return_value = mocked_process

    result = get_labels_from_image("sha256_value", "image_uri")

    for missing_label in missing_labels:
        assert missing_label not in result

    command = "skopeo inspect --cert-dir /var/run/secrets/kubernetes.io/serviceaccount/ image_uri"
    subprocess.Popen.assert_called_once_with(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
    )
    mocked_process.communicate.assert_called_once()

    assert "sha256_value" not in skopeo_failures


@pytest.mark.parametrize(
    "returncode, json_file",
    [
        (
            0,
            "skopeo_malformed_json_file.json",
        )
    ],
)
def test_malformed_json_response(mock_popen, returncode, json_file):
    mocked_process = Mock()
    mocked_process.returncode = returncode
    mocked_process.communicate.return_value = (read_skopeo_fake_data(json_file), b"")
    mock_popen.return_value = mocked_process

    with pytest.raises(SkopeoDataException) as skopeo_exception:
        get_labels_from_image("sha256_value", "image_uri")
    assert "Error: Invalid JSON output" in str(skopeo_exception.value)

    command = "skopeo inspect --cert-dir /var/run/secrets/kubernetes.io/serviceaccount/ image_uri"
    subprocess.Popen.assert_called_once_with(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
    )
    mocked_process.communicate.assert_called_once()

    assert "sha256_value" in skopeo_failures


def test_cache_container_images_labels():
    sha_256 = "sha256_value"
    labels = {"label1": "value1", "label2": "value2"}

    current_time = time.time()

    with patch("time.time") as mock_time:
        mock_time.return_value = current_time
        _cache_container_images_labels(sha_256, labels)

    assert sha_256 in image_label_cache
    assert image_label_cache[sha_256] == (labels, current_time)

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

import os
from pathlib import Path
from runpy import run_path
from typing import Dict

from failure.app import __file__ as app_file

# import pytest


# from pelorus.errors import FailureProviderAuthenticationError

APP = Path(app_file).resolve().as_posix()
PAGER_DUTY_TOKEN = os.environ.get("PAGER_DUTY_TOKEN")


# TODO fix this end 2 end tests
def run_app(arguments: Dict[str, str]) -> None:
    """Run failure app object with desired enviroment variables."""
    try:
        for key, value in arguments.items():
            os.environ[key] = value
        run_path(APP, run_name="__main__")
    finally:
        for key in arguments:
            del os.environ[key]


# @pytest.mark.parametrize("provider", ["wrong", "git_hub", "GITHUB", "GitHub"])
# @pytest.mark.integration
# def test_app_invalid_provider(provider: str):
#     with pytest.raises(ValueError) as error:
#         run_app({"PROVIDER": provider})

#     assert "'tracker_provider' must be in dict_keys" in str(error.value)


# @pytest.mark.integration
# def test_app_pagerduty_error():
#     with pytest.raises(FailureProviderAuthenticationError) as auth_error:
#         run_app({"PROVIDER": "pagerduty"})

#     assert "Check the TOKEN: not authorized, invalid credentials" in str(
#         auth_error.value
#     )


# @pytest.mark.integration
# @pytest.mark.skipif(
#     not PAGER_DUTY_TOKEN,
#     reason="No PagerDuty token set, run export PAGER_DUTY_TOKEN=token",
# )
# def test_app_pagerduty_success():
#     with nullcontext() as context:
#         run_app({"PROVIDER": "pagerduty", "TOKEN": PAGER_DUTY_TOKEN})

#     assert context is None

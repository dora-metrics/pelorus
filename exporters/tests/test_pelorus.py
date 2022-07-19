import os
from datetime import datetime, timezone
from typing import NamedTuple, Optional

import pytest

import pelorus


@pytest.mark.parametrize(
    "start_time,end_time,format",
    [
        ("2020-06-27T03:17:8Z", "2020-06-27T06:17:8Z", "%Y-%m-%dT%H:%M:%SZ"),
        (
            "2020-06-27T03:17:08.00000-0500",
            "2020-06-27T06:17:08.000000-0500",
            "%Y-%m-%dT%H:%M:%S.%f%z",
        ),
    ],
)
def test_convert_date_time_to_timestamp(start_time, end_time, format):
    start_timestamp = 1593227828
    end_timestamp = 1593238628
    three_hours = 10800

    calc_start = pelorus.convert_date_time_to_timestamp(start_time, format)
    assert calc_start == start_timestamp
    calc_end = pelorus.convert_date_time_to_timestamp(end_time, format)
    assert calc_end == end_timestamp
    assert calc_end - calc_start == three_hours


def test_get_app_label():
    os.environ["APP_LABEL"] = "changed"
    assert pelorus.get_app_label() == "changed"
    os.unsetenv("APP_LABEL")


def test_get_prod_label():
    assert pelorus.get_prod_label() == pelorus.DEFAULT_PROD_LABEL
    os.environ["PROD_LABEL"] = "changed"
    assert pelorus.get_prod_label() == "changed"
    os.unsetenv("PROD_LABEL")


def test_missing_configs():
    configs = ["VAR1", "VAR2"]
    assert pelorus.missing_configs(configs)
    os.environ["VAR1"] = "value"
    os.environ["VAR2"] = "value"
    assert not pelorus.missing_configs(configs)


@pytest.mark.parametrize("date_format", [("%Y-%m-%dT%H:%M:%S.%f")])
def test_datetime_conversion_type(date_format):
    d = datetime.now()
    myts = d.replace(tzinfo=timezone.utc).timestamp()
    ts = pelorus.convert_date_time_to_timestamp(d, date_format)
    assert ts is not None
    assert myts == ts


@pytest.mark.parametrize(
    "date_time, timestamp, date_format",
    [("2020-06-27T06:17:08.000000", 1593238628, "%Y-%m-%dT%H:%M:%S.%f")],
)
def test_datetime__as_str_conversion_type(date_time, timestamp, date_format):
    ts = pelorus.convert_date_time_to_timestamp(date_time, date_format)
    assert ts is not None
    assert timestamp == ts


@pytest.mark.parametrize(
    "timestamp, date_time_str", [(1599659116.0, "2020-09-09T13:45:16Z")]
)
def test_timestamp_to_datetime_conversion(timestamp, date_time_str):
    date_time = pelorus.convert_timestamp_to_date_time_str(timestamp)
    assert date_time is not None
    assert date_time == date_time_str


def unset_envs():
    vars = [
        "GIT_USER",
        "GIT_TOKEN",
        "GIT_API",
        "GITHUB_USER",
        "GITHUB_TOKEN",
        "GITHUB_API",
        "USER",
        "TOKEN",
    ]

    for var in vars:
        if pelorus.utils.get_env_var(var):
            del os.environ[var]
        print("%s: %s" % (var, pelorus.utils.get_env_var(var)))


class LegacyVarsArgs(NamedTuple):
    """
    Arguments for upgrade_legacy_vars parametrized testing.
    """

    name: str
    git_user: Optional[str] = None
    git_token: Optional[str] = None
    git_api: Optional[str] = None
    github_user: Optional[str] = None
    github_token: Optional[str] = None
    github_api: Optional[str] = None
    user: Optional[str] = None
    token: Optional[str] = None


@pytest.mark.parametrize(
    "_test_name,git_user,git_token,git_api,github_user,github_token,github_api,user,token",
    [
        LegacyVarsArgs(
            name="github_{user,token,api} work on their own",
            git_user=None,
            git_token=None,
            git_api=None,
            github_user="goodU",
            github_token="goodT",
            github_api="goodA",
            user=None,
            token=None,
        ),
        LegacyVarsArgs(
            name="git_{user,token,api} work on their own",
            git_user="goodU",
            git_token="goodT",
            git_api="goodA",
            github_user=None,
            github_token=None,
            github_api=None,
            user=None,
            token=None,
        ),
        LegacyVarsArgs(
            name="git_* takes precedence over github_*",
            git_user="goodU",
            git_token="goodT",
            git_api="goodA",
            github_user="badU",
            github_token="badT",
            github_api="badA",
            user=None,
            token=None,
        ),
        LegacyVarsArgs(
            name="user, token work on their own",
            git_user=None,
            git_token=None,
            git_api="goodA",
            github_user=None,
            github_token=None,
            github_api=None,
            user="goodU",
            token="goodT",
        ),
        LegacyVarsArgs(
            name="user, token have precedence over git_*",
            git_user="badU",
            git_token="badT",
            git_api="goodA",
            github_user=None,
            github_token=None,
            github_api=None,
            user="goodU",
            token="goodT",
        ),
        LegacyVarsArgs(
            name="user, token have precedence over github_*",
            git_user=None,
            git_token=None,
            git_api="goodA",
            github_user="badU",
            github_token="badT",
            github_api=None,
            user="goodU",
            token="goodT",
        ),
    ],
)
def test_ugprade_legacy_vars(
    _test_name,
    git_user,
    git_token,
    git_api,
    github_user,
    github_token,
    github_api,
    user,
    token,
):
    unset_envs()
    if git_user:
        os.environ["GIT_USER"] = git_user
    if git_token:
        os.environ["GIT_TOKEN"] = git_token
    if git_api:
        os.environ["GIT_API"] = git_api
    if github_user:
        os.environ["GITHUB_USER"] = github_user
    if github_token:
        os.environ["GITHUB_TOKEN"] = github_token
    if github_api:
        os.environ["GITHUB_API"] = github_api
    if user:
        os.environ["USER"] = user
    if token:
        os.environ["TOKEN"] = token
    pelorus.upgrade_legacy_vars()
    assert os.environ["USER"] == "goodU"
    assert os.environ["TOKEN"] == "goodT"
    assert os.environ["GIT_API"] == "goodA"
    unset_envs()

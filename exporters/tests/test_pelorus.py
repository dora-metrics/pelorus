import os
from typing import NamedTuple, Optional

import pytest

import pelorus


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


def unset_envs():
    vars = [
        "GIT_USER",
        "GIT_TOKEN",
        "GIT_API",
        "GITHUB_USER",
        "GITHUB_TOKEN",
        "GITHUB_API",
        "API_USER",
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
    api_user: Optional[str] = None
    token: Optional[str] = None


@pytest.mark.parametrize(
    "_test_name,git_user,git_token,git_api,github_user,github_token,github_api,api_user,token",
    [
        LegacyVarsArgs(
            name="github_{user,token,api} work on their own",
            git_user=None,
            git_token=None,
            git_api=None,
            github_user="goodU",
            github_token="goodT",
            github_api="goodA",
            api_user=None,
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
            api_user=None,
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
            api_user=None,
            token=None,
        ),
        LegacyVarsArgs(
            name="api_user, token work on their own",
            git_user=None,
            git_token=None,
            git_api="goodA",
            github_user=None,
            github_token=None,
            github_api=None,
            api_user="goodU",
            token="goodT",
        ),
        LegacyVarsArgs(
            name="api_user, token have precedence over git_*",
            git_user="badU",
            git_token="badT",
            git_api="goodA",
            github_user=None,
            github_token=None,
            github_api=None,
            api_user="goodU",
            token="goodT",
        ),
        LegacyVarsArgs(
            name="api_user, token have precedence over github_*",
            git_user=None,
            git_token=None,
            git_api="goodA",
            github_user="badU",
            github_token="badT",
            github_api=None,
            api_user="goodU",
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
    api_user,
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
    if api_user:
        os.environ["API_USER"] = api_user
    if token:
        os.environ["TOKEN"] = token
    pelorus.upgrade_legacy_vars()
    assert os.environ["API_USER"] == "goodU"
    assert os.environ["TOKEN"] == "goodT"
    assert os.environ["GIT_API"] == "goodA"
    unset_envs()

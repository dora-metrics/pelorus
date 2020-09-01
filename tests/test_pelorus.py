import os
import pytest
from exporters import pelorus


@pytest.mark.parametrize("start_time,end_time,format",
                         [
                            ('2020-06-27T03:17:8Z', '2020-06-27T06:17:8Z', '%Y-%m-%dT%H:%M:%SZ'),
                            ('2020-06-27T03:17:08.00000-0500', '2020-06-27T06:17:08.000000-0500',
                                                               '%Y-%m-%dT%H:%M:%S.%f%z')
                         ]
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
    assert pelorus.get_app_label() == pelorus.DEFAULT_APP_LABEL
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


@pytest.mark.parametrize("git_user,git_token,git_api,github_user,github_token,github_api",
                         [
                            (None, None, None, 'goodU', 'goodT', 'goodA'),
                            ('goodU', 'goodT', 'goodA', None, None, None),       
                            ('goodU', 'goodT', 'goodA', 'badU', 'badT', 'badA')
                         ]
                         )
def test_ugprade_legacy_vars(git_user, git_token, git_api, github_user, github_token, github_api):
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
    pelorus.upgrade_legacy_vars()
    assert os.environ["GIT_USER"] == 'goodU'
    assert os.environ["GIT_TOKEN"] == 'goodT'
    assert os.environ["GIT_API"] == 'goodA'
    os.unsetenv("GIT_USER")
    os.unsetenv("GIT_TOKEN")
    os.unsetenv("GIT_API")
    os.unsetenv("GITHUB_USER")
    os.unsetenv("GITHUB_TOKEN")
    os.unsetenv("GITHUB_API")

import pytest
import pelorus
from committime.collector_base import CommitMetric


@pytest.mark.parametrize("start_time,end_time,format",
                         [
                             ('2020-06-27T03:17:8Z',
                              '2020-06-27T06:17:8Z', '%Y-%m-%dT%H:%M:%SZ'),
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


# Unit tests for the CommitMetric
@pytest.mark.parametrize("appname", [("pytest")])
def test_commitmetric_initial(appname):
    metric = CommitMetric(appname, None)
    assert metric.repo_url is None
    assert metric.name == appname


@pytest.mark.parametrize("protocol,fqdn,group,project,project_noext",
                         [
                             ('https', 'dogs.git.foo', 'dogs', 'repo.git', 'repo'),
                             ('http', 'noabank.git.foo', 'chase', 'git.git', 'git'),
                             ('ssh', 'git.moos.foo', 'maverick', 'tootsie.git', 'tootsie'),
                             ('notvalid', 'breakme', 'snoopy', 'gtist.git', 'gtist'),
                             ('kmoos', 'myprotocol', 'buffy', 'noext', 'noext'),
                         ]
                         )
def test_commitmetric_repos(protocol, fqdn, group, project, project_noext):
    url = str(protocol + '://' + fqdn + '/' + group + '/' + project)
    metric = CommitMetric("pytest")
    metric.repo_url = url
    assert metric.repo_url is not None
    assert metric.repo_url == url
    metric.parse_repourl()
    assert metric.repo_protocol is not None
    assert metric.repo_fqdn is not None
    assert metric.repo_group is not None
    assert metric.repo_project is not None
    assert metric.repo_protocol == protocol
    assert metric.repo_fqdn == fqdn
    assert metric.repo_combine_protocol_fqdn() == str(protocol + '://' + fqdn)
    test_value = metric.repo_strip_git_from_project()
    assert test_value is not None
    assert test_value == project_noext

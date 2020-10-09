import pytest
import pelorus
from committime.commit_metric import CommitMetric


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
    metric = CommitMetric(appname)
    assert metric.repo_url is None
    assert metric.name == appname
    assert metric.repo_protocol is None
    assert metric.git_fqdn is None
    assert metric.repo_group is None
    assert metric.repo_project is None


@pytest.mark.parametrize("url,project_name",
                         [
                             ('https://dogs.git.foo/dogs/repo.git', 'repo'),
                             ('http://dogs.git.foo/dogs/repo.git', 'repo'),
                             ('http://noabank.git.foo/chase/git.git', 'git'),
                             ('ssh://git.moos.foo/maverick/tootsie.git', 'tootsie'),
                             ('git@github.com:redhat-cop/pelorus.git', 'pelorus'),
                             ('notvalid://breakme/snoopy/gtist.git', 'gtist'),
                             ('kmoos://myprotocol/buffy/noext/noext', 'noext'),
                             ('https://gitlab.com/firstgroup/secondgroup/myrepo.git', 'myrepo')
                         ]
                         )
def test_commitmetric_repos(url, project_name):
    test_name = 'pytest'
    metric = CommitMetric(test_name)
    metric.name == test_name
    assert metric.repo_url is None
    assert metric.repo_protocol is None
    assert metric.git_fqdn is None
    assert metric.repo_group is None
    assert metric.repo_project is None
    metric.repo_url = url
    assert metric.repo_url is not None
    assert metric.repo_url == url
    assert metric.repo_protocol is not None
    assert metric.git_fqdn is not None
    assert metric.repo_group is not None
    assert metric.repo_project is not None
#    assert metric.repo_protocol == protocol
#    assert metric.git_fqdn == fqdn
#    assert metric.git_server == str(protocol + '://' + fqdn)
    assert metric.repo_project == project_name

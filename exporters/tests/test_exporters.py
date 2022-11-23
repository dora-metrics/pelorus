import pytest

from committime.collector_base import CommitMetric


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


@pytest.mark.parametrize(
    "url,repo_protocol,fqdn,project_name",
    [
        ("https://dogs.git.foo/dogs/repo.git", "https", "dogs.git.foo", "repo"),
        ("http://dogs.git.foo/dogs/repo.git", "http", "dogs.git.foo", "repo"),
        ("http://noabank.git.foo/chase/git.git", "http", "noabank.git.foo", "git"),
        ("ssh://git.moos.foo/maverick/tootsie.git", "ssh", "git.moos.foo", "tootsie"),
        ("git@github.com:konveyor/pelorus.git", "ssh", "github.com", "pelorus"),
        ("https://dev.azure.com/azuretest", "https", "dev.azure.com", "azuretest"),
        (
            "https://gitlab.com/firstgroup/secondgroup/myrepo.git",
            "https",
            "gitlab.com",
            "myrepo",
        ),
    ],
)
def test_commitmetric_repos(url, repo_protocol, fqdn, project_name):
    test_name = "pytest"
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
    assert metric.repo_protocol == repo_protocol
    assert metric.git_fqdn is not None
    if metric.repo_url != "https://dev.azure.com/azuretest":
        assert metric.repo_group is not None
    else:
        assert metric.repo_group is None
    assert metric.repo_project is not None
    assert metric.git_fqdn == fqdn
    #    assert metric.git_server == str(protocol + '://' + fqdn)
    assert metric.repo_project == project_name


@pytest.mark.parametrize(
    "malformed_url",
    ["kmoos://myprotocol/buffy/noext/noext", "notvalid://breakme/snoopy/gtist.git"],
)
def test_malformed_git_url(malformed_url):
    test_name = "pytest"
    metric = CommitMetric(test_name)
    metric.name = test_name
    with pytest.raises(ValueError):
        metric.repo_url = malformed_url

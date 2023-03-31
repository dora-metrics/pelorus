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
    assert metric.azure_project is None


@pytest.mark.parametrize(
    "url,repo_protocol,fqdn,project_name,azure_organization,azure_project",
    [
        (
            "git@ssh.dev.azure.com:v3/organization/project/repository/",
            "ssh",
            "ssh.dev.azure.com:v3",
            "repository",
            "organization",
            "project",
        ),
        (
            "git@ssh.dev.azure.com:v3/Organization1Name/Project-Name/the-repository-name/",
            "ssh",
            "ssh.dev.azure.com:v3",
            "the-repository-name",
            "Organization1Name",
            "Project-Name",
        ),
        (
            "https://dev.azure.com/Organization1Name/Project-Name/_git/the-repository-name/",
            "https",
            "dev.azure.com",
            "the-repository-name",
            "Organization1Name",
            "Project-Name",
        ),
        (
            "https://enterprise.custom/Organization1Name/Project-Name/_git/the-repository-name/",
            "https",
            "enterprise.custom",
            "the-repository-name",
            "Organization1Name",
            "Project-Name",
        ),
        (
            "https://dev.azure.com/Organization/Project/_git/repository/",
            "https",
            "dev.azure.com",
            "repository",
            "Organization",
            "Project",
        ),
        (
            "https://dev.azure.com/organization/project/_git/repository/",
            "https",
            "dev.azure.com",
            "repository",
            "organization",
            "project",
        ),
        (
            "https://dev.azure.com:8080/organization/project/_git/repository/",
            "https",
            "dev.azure.com",
            "repository",
            "organization",
            "project",
        ),
        (
            "http://dev.azure.com:8080/organization/project/_git/repository/",
            "http",
            "dev.azure.com",
            "repository",
            "organization",
            "project",
        ),
    ],
)
def test_commitmetric_azure_repos(
    url, repo_protocol, fqdn, project_name, azure_organization, azure_project
):
    test_name = "pytest"
    metric = CommitMetric(test_name)
    assert metric.repo_url is None
    assert metric.repo_protocol is None
    assert metric.git_fqdn is None
    assert metric.repo_group is None
    assert metric.repo_project is None
    assert metric.azure_project is None
    metric.repo_url = url
    assert metric.repo_url == url.strip("/")
    assert metric.repo_protocol == repo_protocol
    assert metric.repo_group == azure_organization
    assert metric.git_fqdn == fqdn
    assert f"{repo_protocol}://{fqdn}" in metric.git_server
    assert metric.repo_project == project_name
    assert metric.azure_project == azure_project


@pytest.mark.parametrize(
    "url,repo_protocol,fqdn,project_name,azure_organization,azure_project,user",
    [
        (
            "https://User2@dev.azure.com/Organization1Name/Project-Name/_git/the-repository-name/",
            "https",
            "dev.azure.com",
            "the-repository-name",
            "Organization1Name",
            "Project-Name",
            "User2",
        ),
        (
            "https://Bruce@enterprise.custom/Organization1Name/Project-Name/_git/the-repository-name/",
            "https",
            "enterprise.custom",
            "the-repository-name",
            "Organization1Name",
            "Project-Name",
            "Bruce",
        ),
        (
            "https://User@dev.azure.com/Organization/Project/_git/repository/",
            "https",
            "dev.azure.com",
            "repository",
            "Organization",
            "Project",
            "User",
        ),
        (
            "https://user@dev.azure.com/organization/project/_git/repository/",
            "https",
            "dev.azure.com",
            "repository",
            "organization",
            "project",
            "user",
        ),
        (
            "https://user@dev.azure.com:8080/organization/project/_git/repository/",
            "https",
            "dev.azure.com",
            "repository",
            "organization",
            "project",
            "user",
        ),
        (
            "http://user@dev.azure.com:8080/organization/project/_git/repository/",
            "http",
            "dev.azure.com",
            "repository",
            "organization",
            "project",
            "user",
        ),
    ],
)
def test_commitmetric_azure_repos_with_user(
    url, repo_protocol, fqdn, project_name, azure_organization, azure_project, user
):
    test_name = "pytest"
    metric = CommitMetric(test_name)
    assert metric.repo_url is None
    assert metric.repo_protocol is None
    assert metric.git_fqdn is None
    assert metric.repo_group is None
    assert metric.repo_project is None
    assert metric.azure_project is None
    metric.repo_url = url
    assert metric.repo_url == url.strip("/")
    assert metric.repo_protocol == repo_protocol
    assert metric.repo_group == azure_organization
    assert metric.git_fqdn == fqdn
    assert f"{repo_protocol}://{fqdn}" in metric.git_server
    assert metric.repo_project == project_name
    assert metric.azure_project == azure_project


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

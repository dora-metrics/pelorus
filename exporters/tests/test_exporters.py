import pytest

from committime import CommitMetric


def test_commitmetric_initial():
    metric = CommitMetric("pytest")
    assert metric.repo_url is None
    assert metric.name == "pytest"
    assert metric.repo_protocol is None
    assert metric.git_fqdn is None
    assert metric.repo_group is None
    assert metric.repo_project is None


@pytest.mark.parametrize(
    "url,repo_protocol,fqdn,project_name,repo_group",
    [
        ("https://dogs.git.foo/dogs/repo.git", "https", "dogs.git.foo", "repo", "dogs"),
        ("http://dogs.git.foo/dogs/repo.git", "http", "dogs.git.foo", "repo", "dogs"),
        ("http://noabank.git.foo/chase/git.git", "http", "noabank.git.foo", "git", "chase"),
        ("ssh://git.moos.foo/maverick/tootsie.git", "ssh", "git.moos.foo", "tootsie", "maverick"),
        ("git@github.com:dora-metrics/pelorus.git", "ssh", "github.com", "pelorus", "dora-metrics"),
        ("https://dev.azure.com/azuretest", "https", "dev.azure.com", "azuretest", None),
        (
            "https://gitlab.com/firstgroup/secondgroup/myrepo.git",
            "https",
            "gitlab.com",
            "myrepo",
            "/gitlab.com/firstgroup/secondgroup",
        ),
    ],
)
def test_commitmetric_repos(url, repo_protocol, fqdn, project_name, repo_group):
    metric = CommitMetric("pytest")
    metric.repo_url = url
    assert metric.repo_url == url
    assert metric.repo_protocol == repo_protocol
    assert metric.git_fqdn == fqdn
    assert metric.repo_project == project_name
    assert metric.repo_group == repo_group
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
    metric = CommitMetric("pytest")
    metric.repo_url = url
    assert metric.repo_url == url.strip("/")
    assert metric.repo_protocol == repo_protocol
    assert metric.repo_group == azure_organization
    assert metric.git_fqdn == fqdn
    assert f"{repo_protocol}://{fqdn}" in metric.git_server
    assert metric.repo_project == project_name
    assert metric.azure_project == azure_project


@pytest.mark.parametrize(
    "url,repo_protocol,fqdn,project_name,azure_organization,azure_project",
    [
        (
            "https://User2@dev.azure.com/Organization1Name/Project-Name/_git/the-repository-name/",
            "https",
            "dev.azure.com",
            "the-repository-name",
            "Organization1Name",
            "Project-Name",
        ),
        (
            "https://Bruce@enterprise.custom/Organization1Name/Project-Name/_git/the-repository-name/",
            "https",
            "enterprise.custom",
            "the-repository-name",
            "Organization1Name",
            "Project-Name",
        ),
        (
            "https://User@dev.azure.com/Organization/Project/_git/repository/",
            "https",
            "dev.azure.com",
            "repository",
            "Organization",
            "Project",
        ),
        (
            "https://user@dev.azure.com/organization/project/_git/repository/",
            "https",
            "dev.azure.com",
            "repository",
            "organization",
            "project",
        ),
        (
            "https://user@dev.azure.com:8080/organization/project/_git/repository/",
            "https",
            "dev.azure.com",
            "repository",
            "organization",
            "project",
        ),
        (
            "http://user@dev.azure.com:8080/organization/project/_git/repository/",
            "http",
            "dev.azure.com",
            "repository",
            "organization",
            "project",
        ),
    ],
)
def test_commitmetric_azure_repos_with_user(
    url, repo_protocol, fqdn, project_name, azure_organization, azure_project
):
    metric = CommitMetric("pytest")
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
    metric = CommitMetric("pytest")
    with pytest.raises(ValueError):
        metric.repo_url = malformed_url

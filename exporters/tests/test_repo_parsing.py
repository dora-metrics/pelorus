import pytest

from committime import GitRepo


@pytest.mark.parametrize(
    "url,protocol,fqdn,project_name",
    [
        ("https://dogs.git.foo/dogs/repo.git", "https", "dogs.git.foo", "repo"),
        ("http://dogs.git.foo/dogs/repo.git", "http", "dogs.git.foo", "repo"),
        ("http://noabank.git.foo/chase/git.git", "http", "noabank.git.foo", "git"),
        ("ssh://git.moos.foo/maverick/tootsie.git", "ssh", "git.moos.foo", "tootsie"),
        ("git@github.com:konveyor/pelorus.git", "ssh", "github.com", "pelorus"),
        (
            "https://dev.azure.com/azuretest",
            "https",
            "dev.azure.com",
            "azuretest",
        ),
        (
            "https://gitlab.com/firstgroup/secondgroup/myrepo.git",
            "https",
            "gitlab.com",
            "myrepo",
        ),
    ],
)
def test_gitrepo_parsing(url: str, protocol: str, fqdn: str, project_name: str):
    "Tests that git url parsing works as expected."
    repo = GitRepo.from_url(url)
    assert repo.url == url
    assert repo.protocol == protocol
    assert repo.fqdn == fqdn

    if fqdn == "dev.azure.com":
        # azure does not have groups
        assert repo.group is None
    else:
        assert repo.group is not None

    assert repo.project == project_name


@pytest.mark.parametrize(
    "malformed_url",
    ["kmoos://myprotocol/buffy/noext/noext", "notvalid://breakme/snoopy/gtist.git"],
)
def test_malformed_git_url(malformed_url: str):
    with pytest.raises(ValueError):
        GitRepo.from_url(malformed_url)

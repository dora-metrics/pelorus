import logging

import attrs
import requests
from attrs import define, field

from committime import CommitInfo
from pelorus.config.converters import pass_through
from pelorus.utils import Url, get_nested, set_up_requests_session
from provider_common.github import parse_datetime

from .collector_base import AbstractGitCommitCollector, UnsupportedGITProvider

DEFAULT_GITHUB_API = Url.parse("api.github.com")


@define(kw_only=True)
class GitHubCommitCollector(AbstractGitCommitCollector):
    session: requests.Session = field(factory=requests.Session, init=False)

    # overrides with default
    git_api: Url = field(
        default=DEFAULT_GITHUB_API,
        converter=attrs.converters.optional(pass_through(Url, Url.parse)),
    )

    _path_pattern = "/repos/{group}/{project}/commits/{hash}"

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        set_up_requests_session(
            self.session, self.tls_verify, username=self.username, token=self.token
        )

    def get_commit_time(self, info: CommitInfo):
        repo, hash = info
        git_server = repo.fqdn
        if (
            "gitea" in git_server
            or "gitlab" in git_server
            or "bitbucket" in git_server
            or "azure" in git_server
        ):
            raise UnsupportedGITProvider(
                "Skipping non GitHub server, found %s" % (git_server)
            )

        path = self._path_pattern.format(
            group=repo.group,
            project=repo.project,
            hash=hash,
        )
        url = self.git_api._replace(path=path).url
        response = self.session.get(url)
        if response.status_code != 200:
            # This will occur when trying to make an API call to non-Github
            logging.warning(
                "Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s",
                hash,
                repo.fqdn,
                response.status_code,
            )
            return None
        try:
            commit = response.json()
            commit_time: str = get_nested(
                commit,
                "commit.committer.date",
            )
            return parse_datetime(commit_time)
        except Exception:
            logging.error(
                "Failed processing commit time for build %s",
                exc_info=True,
            )
            raise

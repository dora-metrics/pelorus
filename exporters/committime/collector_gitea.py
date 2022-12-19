import logging

import attrs
import requests
from attrs import define, field

from committime import CommitInfo
from pelorus.config.converters import pass_through
from pelorus.timeutil import parse_assuming_utc, second_precision
from pelorus.utils import Url, set_up_requests_session

from .collector_base import AbstractGitCommitCollector, UnsupportedGITProvider

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

DEFAULT_GITEA_API = Url.parse("https://try.gitea.io")


@define(kw_only=True)
class GiteaCommitCollector(AbstractGitCommitCollector):

    session: requests.Session = field(factory=requests.Session, init=False)

    # overrides with default
    git_api: Url = field(
        default=DEFAULT_GITEA_API,
        converter=attrs.converters.optional(pass_through(Url, Url.parse)),
    )

    _path_template = "/api/v1/repos/{group}/{project}/git/commits/{hash}"

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        set_up_requests_session(
            self.session, self.tls_verify, username=self.username, token=self.token
        )

    def get_commit_time(self, info: CommitInfo):
        """Method called to collect data and send to Prometheus"""

        repo, hash = info

        git_server = repo.server

        if (
            "github" in git_server
            or "bitbucket" in git_server
            or "gitlab" in git_server
            or "azure" in git_server
        ):
            raise UnsupportedGITProvider(
                "Skipping non Gitea server, found %s" % (git_server)
            )

        path = self._path_template.format(
            group=repo.group,
            project=repo.project,
            hash=hash,
        )
        url = self.git_api._replace(path=path).url
        logging.info("URL %s" % (url))
        response = self.session.get(url, auth=(self.username, self.token))
        logging.info("response %s", response)
        if response.status_code != 200:
            # This will occur when trying to make an API call to non-Github
            logging.warning(
                "Unable to retrieve commit time for hash: %s, url: %s. Got http code: %s",
                hash,
                repo.url,
                response.status_code,
            )
            return None

        try:
            commit = response.json()
            commit_time_str: str = commit["commit"]["committer"]["date"]

            commit_time = parse_assuming_utc(commit_time_str, format=_DATETIME_FORMAT)
            commit_time = second_precision(commit_time)

            logging.debug("metric.commit_time %s", commit_time)
            return commit_time
        except Exception:
            logging.error(
                "Failed processing commit time",
                exc_info=True,
            )
            raise

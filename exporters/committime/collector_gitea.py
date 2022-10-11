import logging
from functools import partial

import attrs
import requests
from attrs import define, field

from committime import CommitMetric
from pelorus.config.converters import pass_through
from pelorus.timeutil import parse_assuming_utc, second_precision
from pelorus.utils import Url, set_up_requests_session

from .collector_base import AbstractCommitCollector, UnsupportedGITProvider

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

DEFAULT_GITEA_API = Url.parse("https://try.gitea.io")


@define(kw_only=True)
class GiteaCommitCollector(AbstractCommitCollector):

    session: requests.Session = field(factory=requests.Session, init=False)

    # overrides with default
    git_api: Url = field(
        default=DEFAULT_GITEA_API,
        converter=attrs.converters.optional(
            pass_through(Url, partial(Url.parse, default_scheme="https"))
        ),
    )

    _path_template = "{group}/{project}/git/commits/{hash}"

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        set_up_requests_session(
            self.session, self.tls_verify, username=self.username, token=self.token
        )

    # base class impl
    def get_commit_time(self, metric: CommitMetric):
        """Method called to collect data and send to Prometheus"""

        git_server = metric.git_server

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
            group=metric.repo_group,
            project=metric.repo_project,
            hash=metric.commit_hash,
        )
        url = self.git_api._replace(path=path).url
        logging.info("URL %s" % (url))
        response = self.session.get(url, auth=(self.username, self.token))
        logging.info("response %s", response)
        if response.status_code != 200:
            # This will occur when trying to make an API call to non-Github
            logging.warning(
                "Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s"
                % (
                    metric.build_name,
                    metric.commit_hash,
                    metric.repo_url,
                    str(response.status_code),
                )
            )
        else:
            commit = response.json()
            try:
                commit_time_str: str = commit["commit"]["committer"]["date"]
                metric.commit_time = commit_time_str

                commit_time = parse_assuming_utc(
                    commit_time_str, format=_DATETIME_FORMAT
                )
                commit_time = second_precision(commit_time)

                logging.debug("metric.commit_time %s", commit_time)
                metric.commit_timestamp = commit_time.timestamp()
            except Exception:
                logging.error(
                    "Failed processing commit time for build %s" % metric.build_name,
                    exc_info=True,
                )
                logging.debug(commit)
                raise
        return metric

import logging

import attrs
import requests
from attrs import define, field

from committime import CommitMetric
from pelorus.config.converters import pass_through
from pelorus.timeutil import ISO_ZULU_FMT, parse_assuming_utc, second_precision
from pelorus.utils import Url, set_up_requests_session

from .collector_base import AbstractCommitCollector, check_provider_support

DEFAULT_GITEA_API = Url.parse("https://try.gitea.io")


@define(kw_only=True)
class GiteaCommitCollector(AbstractCommitCollector):
    session: requests.Session = field(factory=requests.Session, init=False)

    # overrides with default
    git_api: Url = field(
        default=DEFAULT_GITEA_API,
        converter=attrs.converters.optional(pass_through(Url, Url.parse)),
    )

    _path_template = "/api/v1/repos/{group}/{project}/git/commits/{hash}"

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.git_api == DEFAULT_GITEA_API:
            logging.warning(
                "GIT_API not set — using default %s (a public demo instance). "
                "Set GIT_API to your Gitea server URL.",
                DEFAULT_GITEA_API,
            )
        set_up_requests_session(
            self.session, self.tls_verify, username=self.username, token=self.token
        )

    def get_commit_time(self, metric: CommitMetric):
        """Fetch commit timestamp from Gitea API for the given metric."""

        git_server = metric.git_server

        check_provider_support(git_server, "gitea")

        path = self._path_template.format(
            group=metric.repo_group,
            project=metric.repo_project,
            hash=metric.commit_hash,
        )
        url = self.git_api._replace(path=path).url
        logging.debug("URL %s", url)
        response = self.session.get(url, timeout=30)
        logging.debug("response status=%s reason=%s", response.status_code, response.reason)
        if response.status_code != 200:
            log_level = logging.ERROR if response.status_code in (401, 403) else logging.WARNING
            logging.log(
                log_level,
                "Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s",
                metric.build_name,
                metric.commit_hash,
                metric.repo_url,
                response.status_code,
            )
            return metric
        try:
            commit = response.json()
        except requests.JSONDecodeError:
            logging.error(
                "Invalid JSON response for build: %s, hash: %s, url: %s",
                metric.build_name,
                metric.commit_hash,
                metric.repo_url,
                exc_info=True,
            )
            return metric
        try:
            commit_time_str: str = commit["commit"]["committer"]["date"]
            metric.commit_time = commit_time_str

            commit_time = parse_assuming_utc(
                commit_time_str, format=ISO_ZULU_FMT
            )
            commit_time = second_precision(commit_time)

            logging.debug("metric.commit_time %s", commit_time)
            metric.commit_timestamp = commit_time.timestamp()
            metric.commit_link = commit["html_url"]
        except Exception:
            logging.error(
                "Failed processing commit time for build %s",
                metric.build_name,
                exc_info=True,
            )
            logging.debug("Raw commit response keys: %s", list(commit.keys()) if isinstance(commit, dict) else type(commit).__name__)
            raise
        return metric

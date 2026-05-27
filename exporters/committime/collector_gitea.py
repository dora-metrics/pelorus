import logging

import attrs
import requests
from attrs import define, field

from committime import CommitMetric
from pelorus.config.converters import pass_through
from pelorus.timeutil import ISO_ZULU_FMT, parse_assuming_utc, second_precision
from pelorus.utils import Url, set_up_requests_session

from .collector_base import AbstractCommitCollector, check_provider_support, fetch_commit_json, git_api_errors

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

        check_provider_support(metric.git_server, "gitea")

        path = self._path_template.format(
            group=metric.repo_group,
            project=metric.repo_project,
            hash=metric.commit_hash,
        )
        url = self.git_api._replace(path=path).url
        commit = fetch_commit_json(self.session, url, metric, self._API_TIMEOUT, "Gitea")
        if commit is None:
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
        except (KeyError, TypeError, AttributeError, ValueError):
            git_api_errors.inc()
            logging.error(
                "Failed processing commit time for build %s",
                metric.build_name,
                exc_info=True,
            )
            commit_info = (
                list(commit.keys()) if isinstance(commit, dict)
                else type(commit).__name__
            )
            logging.debug("Raw commit response keys: %s", commit_info)
            raise
        return metric

import logging

import attrs
import requests
from attrs import define, field

from committime import CommitMetric
from pelorus.config.converters import pass_through
from pelorus.utils import Url, set_up_requests_session
from provider_common.github import parse_datetime

from .collector_base import AbstractCommitCollector, check_provider_support, fetch_commit_json, git_api_errors

DEFAULT_GITHUB_API = Url.parse("api.github.com")


@define(kw_only=True)
class GitHubCommitCollector(AbstractCommitCollector):
    session: requests.Session = field(factory=requests.Session, init=False)

    # overrides with default
    git_api: Url = field(
        default=DEFAULT_GITHUB_API,
        converter=attrs.converters.optional(pass_through(Url, Url.parse)),
    )

    _path_template = "/repos/{group}/{project}/commits/{hash}"

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        set_up_requests_session(
            self.session, self.tls_verify, username=self.username, token=self.token
        )

    def get_commit_time(self, metric: CommitMetric):
        """Fetch commit timestamp from GitHub API for the given metric."""
        check_provider_support(metric.git_fqdn, "github")

        path = self._path_template.format(
            group=metric.repo_group,
            project=metric.repo_project,
            hash=metric.commit_hash,
        )
        url = self.git_api._replace(path=path).url
        commit = fetch_commit_json(self.session, url, metric, self._API_TIMEOUT, "GitHub")
        if commit is None:
            return metric
        try:
            metric.commit_time = commit["commit"]["committer"]["date"]
            metric.commit_timestamp = parse_datetime(metric.commit_time).timestamp()
            metric.commit_link = commit["html_url"]
            logging.debug("Set all github commit metrics: %s", metric)
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

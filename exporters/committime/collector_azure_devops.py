import logging
from datetime import datetime

from attrs import converters, define, field
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

from committime import CommitMetric
from pelorus.config.converters import pass_through
from pelorus.utils import Url

from .collector_base import AbstractCommitCollector, check_provider_support

DEFAULT_AZURE_API = Url.parse("https://dev.azure.com")


@define(kw_only=True)
class AzureDevOpsCommitCollector(AbstractCommitCollector):
    # overrides with default
    git_api: Url = field(
        default=DEFAULT_AZURE_API,
        converter=converters.optional(pass_through(Url, Url.parse)),
    )

    # Cache of git_clients keyed by organization_url to avoid reconnecting per commit
    _git_clients: dict = field(factory=dict, init=False)

    def _get_git_client(self, organization_url: str):
        """Get or create a cached git client for the given organization URL."""
        if organization_url not in self._git_clients:
            credentials = BasicAuthentication("", self.token)
            connection = Connection(base_url=organization_url, creds=credentials)
            self._git_clients[organization_url] = connection.clients.get_git_client()
        return self._git_clients[organization_url]

    def get_commit_time(self, metric: CommitMetric):
        """Fetch commit timestamp from Azure DevOps API for the given metric."""
        git_server = metric.git_fqdn

        check_provider_support(git_server, "azure")
        logging.debug("metric.repo_project %s", metric.repo_project)
        logging.debug("metric.git_server %s", metric.git_server)

        organization_url = (
            self.git_api.url + "/" + metric.repo_group
            if metric.repo_group and "/" + metric.repo_group not in self.git_api.url
            else self.git_api.url
        )

        git_client = self._get_git_client(organization_url)

        commit = git_client.get_commit(
            commit_id=metric.commit_hash,
            repository_id=metric.repo_project,
            project=metric.azure_project
            if metric.azure_project
            else metric.repo_project,
        )

        if hasattr(commit, "innerException"):
            logging.warning(
                "Unable to retrieve commit time for build: %s, hash: %s, url: %s. Azure DevOps error: %s",
                metric.build_name,
                metric.commit_hash,
                metric.repo_url,
                getattr(commit, "message", "unknown"),
            )
            return metric

        try:
            timestamp: datetime = commit.committer.date
            timestamp = timestamp.replace(microsecond=0)
            logging.debug("Commit %s", timestamp)
            metric.commit_time = timestamp.isoformat("T", "auto")
            logging.debug("metric.commit_time %s", timestamp)
            metric.commit_timestamp = timestamp.timestamp()
            metric.commit_link = metric.repo_url
        except Exception:
            logging.error(
                "Failed processing commit time for build %s",
                metric.build_name,
                exc_info=True,
            )
            logging.debug("Failed to process commit: %s", commit.commit_id if hasattr(commit, 'commit_id') else 'unknown')
            raise
        return metric

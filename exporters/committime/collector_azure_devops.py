import logging
from datetime import datetime

from attrs import converters, define, field
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

from committime import CommitMetric
from pelorus.config.converters import pass_through
from pelorus.utils import Url

from .collector_base import AbstractCommitCollector, UnsupportedGITProvider

DEFAULT_AZURE_API = Url.parse("https://dev.azure.com")


@define(kw_only=True)
class AzureDevOpsCommitCollector(AbstractCommitCollector):
    collector_name = "Azure-DevOps"

    # overrides with default
    git_api: Url = field(
        default=DEFAULT_AZURE_API,
        converter=converters.optional(pass_through(Url, Url.parse)),
    )

    # base class impl
    def get_commit_time(self, metric: CommitMetric):
        """Method called to collect data and send to Prometheus"""
        git_server = metric.git_fqdn

        if (
            "github" in git_server
            or "bitbucket" in git_server
            or "gitlab" in git_server
            or "gitea" in git_server
        ):
            raise UnsupportedGITProvider(
                "Skipping non Azure DevOps server, found %s" % (git_server)
            )
        logging.debug("metric.repo_project %s" % (metric.repo_project))
        logging.debug("metric.git_server %s" % (metric.git_server))

        # Fill in with your personal access token and org URL
        # personal_access_token = 'YOURPAT'
        # organization_url = 'https://dev.azure.com/YOURORG'
        personal_access_token = self.token
        organization_url = (
            self.git_api.url + "/" + metric.repo_group
            if metric.repo_group and "/" + metric.repo_group not in self.git_api.url
            else self.git_api.url
        )

        # Create a connection to the org
        credentials = BasicAuthentication("", personal_access_token)
        connection = Connection(base_url=organization_url, creds=credentials)

        # Get a client (the "git" client provides access to commits)
        git_client = connection.clients.get_git_client()

        commit = git_client.get_commit(
            commit_id=metric.commit_hash,
            repository_id=metric.repo_project,
            project=metric.azure_project
            if metric.azure_project
            else metric.repo_project,
        )

        timestamp: datetime = commit.committer.date
        timestamp = timestamp.replace(microsecond=0)  # second precision

        logging.debug("Commit %s", timestamp)
        if hasattr(commit, "innerExepction"):
            # This will occur when trying to make an API call to non-Github
            logging.warning(
                "Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s"
                % (
                    metric.build_name,
                    metric.commit_hash,
                    metric.repo_url,
                    str(commit.message),
                )
            )
        else:
            try:
                metric.commit_time = timestamp.isoformat("T", "auto")
                logging.info("metric.commit_time %s", timestamp)
                metric.commit_timestamp = (
                    timestamp.timestamp()
                )  # hopefully they haven't provided a naive datetime
            except Exception:
                logging.error(
                    "Failed processing commit time for build %s" % metric.build_name,
                    exc_info=True,
                )
                logging.debug(commit)
                raise
        return metric

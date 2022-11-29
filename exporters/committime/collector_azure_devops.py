import logging
from datetime import datetime

from attrs import converters, define, field
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

from committime import CommitInfo
from pelorus.config.converters import pass_through
from pelorus.timeutil import second_precision
from pelorus.utils import Url

from .collector_base import AbstractGitCommitCollector, UnsupportedGITProvider

DEFAULT_AZURE_API = Url.parse("https://dev.azure.com")


@define(kw_only=True)
class AzureDevOpsCommitCollector(AbstractGitCommitCollector):
    collector_name = "Azure-DevOps"

    # overrides with default
    git_api: Url = field(
        default=DEFAULT_AZURE_API,
        converter=converters.optional(pass_through(Url, Url.parse)),
    )

    def get_commit_time(self, commit_input: CommitInfo):
        git_server = commit_input.repo.fqdn

        if (
            "github" in git_server
            or "bitbucket" in git_server
            or "gitlab" in git_server
            or "gitea" in git_server
        ):
            raise UnsupportedGITProvider(
                "Skipping non Azure DevOps server, found %s" % (git_server)
            )

        logging.debug("metric.repo_project %s", commit_input.repo.project)

        # Fill in with your personal access token and org URL
        # personal_access_token = 'YOURPAT'
        # organization_url = 'https://dev.azure.com/YOURORG'
        personal_access_token = self.token
        organization_url = self.git_api.url

        credentials = BasicAuthentication("", personal_access_token)
        connection = Connection(base_url=organization_url, creds=credentials)

        git_client = connection.clients.get_git_client()

        commit = git_client.get_commit(
            commit_id=commit_input.commit_hash,
            repository_id=commit_input.repo.project,
            project=commit_input.repo.project,
        )

        if hasattr(commit, "innerExepction"):
            logging.warning(
                "Unable to retrieve commit time for hash: %s, url: %s. Got http code: %s",
                commit_input.commit_hash,
                commit_input.repo_url,
                commit.message,
            )
            return None
        timestamp: datetime = second_precision(commit.committer.date)

        logging.debug("Commit %s:%s", commit_input.commit_hash, timestamp)
        return timestamp  # hopefully they haven't provided a naive datetime

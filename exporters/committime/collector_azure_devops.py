import logging

import requests
from azure.devops.connection import Connection
from collector_base import AbstractCommitCollector, UnsupportedGITProvider
from msrest.authentication import BasicAuthentication

import pelorus


class AzureDevOpsCommitCollector(AbstractCommitCollector):
    def __init__(self, kube_client, username, token, namespaces, apps, git_api):
        super().__init__(
            kube_client,
            username,
            token,
            namespaces,
            apps,
            "Azure-DevOps",
            "%Y-%m-%dT%H:%M:%S",
            git_api,
        )

    # base class impl
    def get_commit_time(self, metric):
        """Method called to collect data and send to Prometheus"""
        git_server = self._git_api

        if (
            "github" in git_server
            or "bitbucket" in git_server
            or "gitlab" in git_server
            or "gitea" in git_server
        ):
            raise UnsupportedGITProvider(
                "Skipping non Azure DevOps server, found %s" % (git_server)
            )

        session = requests.Session()
        session.verify = False

        logging.debug("metric.repo_project %s" % (metric.repo_project))
        logging.debug("metric.git_api %s" % (self._git_api))

        # Private or personal token
        # Fill in with your personal access token and org URL
        personal_access_token = self._token
        organization_url = self._git_api

        # Create a connection to the org
        credentials = BasicAuthentication("", personal_access_token)
        connection = Connection(base_url=organization_url, creds=credentials)

        # Get a client (the "git" client provides access to commits)
        git_client = connection.clients.get_git_client()

        commit = git_client.get_commit(
            commit_id=metric.commit_hash,
            repository_id=metric.repo_project,
            project=metric.repo_project,
        )
        logging.debug("Commit %s" % ((commit.committer.date).isoformat("T", "auto")))
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
                metric.commit_time = commit.committer.date.isoformat("T", "auto")
                logging.info("metric.commit_time %s" % (str(metric.commit_time)[:19]))
                logging.info("self._timedate_format %s" % (self._timedate_format))
                metric.commit_timestamp = pelorus.convert_date_time_to_timestamp(
                    (str(metric.commit_time)[:19]), self._timedate_format
                )
            except Exception:
                logging.error(
                    "Failed processing commit time for build %s" % metric.build_name,
                    exc_info=True,
                )
                logging.debug(commit)
                raise
        return metric

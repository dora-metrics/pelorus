import gitlab
import requests
import logging
import pelorus
from collector_base import AbstractCommitCollector
# import urllib3
# urllib3.disable_warnings()


class GitLabCommitCollector(AbstractCommitCollector):

    def __init__(self, kube_client, username, token, namespaces, apps):
        super().__init__(kube_client, username, token, namespaces, apps, 'GitLab', '%Y-%m-%dT%H:%M:%S.%f%z')

    # base class impl
    def get_commit_time(self, metric):
        """Method called to collect data and send to Prometheus"""
        session = requests.Session()
        session.verify = False

        project_name = metric.repo_project
        git_server = metric.git_server

        if "github" in git_server or "bitbucket" in git_server:
            logging.warn("Skipping non GitLab server, found %s" % (git_server))
            return None

        # Private or personal token
        gl = gitlab.Gitlab(git_server, private_token=self._token, api_version=4, session=session)
        # oauth token authentication
        # gl = gitlab.Gitlab(git_server, oauth_token='my_long_token_here', api_version=4, session=session)

        # get the project id from the map by search for the project_name
        project = None
        try:
            logging.debug("Searching for project: %s" % (project_name))
            project_map = gl.projects.list(search=project_name)
            project = project_map[0]
        except Exception:
            logging.error("Failed to find project: %s, repo: %s for build %s" % (
                metric.repo_url, project_name, metric.build_name), exc_info=True)
            raise
        # Using the project id, get the project
        if project is None:
            raise TypeError("Failed to find repo project: %s, for build %s" % (metric.repo_url, metric.build_name))
        try:
            # get the commit from the project using the hash
            commit = project.commits.get(metric.commit_hash)
            # get the commit date/time
            metric.commit_time = commit.committed_date
            # set the timestamp after conversion
            metric.commit_timestamp = pelorus.convert_date_time_to_timestamp(metric.commit_time, self._timedate_format)
        except Exception:
            logging.error("Failed processing commit time for build %s" % metric.build_name, exc_info=True)
            logging.debug(commit)
            raise
        return metric

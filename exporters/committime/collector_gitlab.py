import gitlab
import requests
import logging
import pelorus
from collector_base import AbstractCommitCollector
# import urllib3
# urllib3.disable_warnings()


class GitLabCommitCollector(AbstractCommitCollector):

    def __init__(self, username, token, namespaces, apps):
        super().__init__(username, token, namespaces, apps, "GitLab")

    # base class impl
    def get_commit_time(self, metric):
        """Method called to collect data and send to Prometheus"""
        session = requests.Session()
        session.verify = False

        uri = metric.repo_url
        url_tokens = uri.split("/")
        protocol = url_tokens[0]
        server = url_tokens[2]
        # group = url_tokens[3]
        project = url_tokens[4]
        project_name = project.strip('.git')

        for t in url_tokens:
            logging.debug(t)

        git_server = protocol + "//" + server

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
                uri, project_name, metric.build_name), exc_info=True)
            raise
        # Using the project id, get the project
        if project is None:
            logging.error("Failed to find repo project: %s, for build %s" % (uri, metric.build_name), exc_info=True)
            raise
        try:
            # get the commit from the project using the hash
            commit = project.commits.get(metric.commit_hash)
            # get the commit date/time
            metric.commit_time = commit.committed_date
            # set the timestamp after conversion
            metric.commit_timestamp = pelorus.convert_date_time_with_utc_offset_to_timestamp(metric.commit_time)
        except Exception:
            logging.error("Failed processing commit time for build %s" % metric.build_name, exc_info=True)
            raise
        return metric

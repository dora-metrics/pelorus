import gitlab
import requests
import logging
import pelorus
from datetime import datetime, timedelta
from collector_base import AbstractCommitCollector
import urllib3
urllib3.disable_warnings()


class GitLabCommitCollector(AbstractCommitCollector):

    __project_maps = {}
    __map_expire_seconds = 900
    __map_expire = datetime.now() + timedelta(seconds=__map_expire_seconds)

    def __init__(self, username, token, namespaces, apps):
        super().__init__(username, token, namespaces, apps, "GitLab")

    def gitlab_project_map(self, gl_projects):
        """Gets the GitLab server project map."""
        if datetime.now() > self.__map_expire:
            # map has expired, so rebuild it.
            logging.debug("Project map expired.")
            self.__project_maps = {}

        if self.__project_maps is None or len(self.__project_maps) == 0:
            logging.debug("Building new project map.")
            self.__map_expire = datetime.now() + timedelta(seconds=self.__map_expire_seconds)
            self.build_project_map(gl_projects)
        else:
            logging.debug("Using cached project map.")

        return self.__project_maps

    def build_project_map(self, gl_projects):
        """Builds a new GitLab project map from the GitLab instance."""
        for project in gl_projects:
            self.__project_maps[project.http_url_to_repo] = project.id

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

        # get the project id from the map
        try:
            project_map = self.gitlab_project_map(gl.projects.list(all=True))
            if len(project_map) == 0:
                logging.error("Unable to build project map from GitLab server", exc_info=True)
                raise
            project_id = project_map[uri]
        except Exception:
            logging.error("Failed to find repo project id: %s, for build %s" % (uri, metric.build_name), exc_info=True)
            raise
        # Using the project id, get the project
        project = gl.projects.get(project_id)
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

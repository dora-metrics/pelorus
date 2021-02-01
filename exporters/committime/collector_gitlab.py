import gitlab
import requests
import logging
import pelorus
from collector_base import AbstractCommitCollector


class GitLabCommitCollector(AbstractCommitCollector):

    def __init__(self, kube_client, git_provider_info, exporter_opts):
        git_provider_info.timedate_format = '%Y-%m-%dT%H:%M:%S.%f%z'
        git_provider_info.collector_name = 'GitLab'
        # disable urllib3 request warnings
        requests.packages.urllib3.disable_warnings()
        self._projects = {}  # Map that will hold the Gitlab projects found
        super().__init__(kube_client, git_provider_info, exporter_opts)

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

        # get the project id from the map by search for the project_name
        # project_name must be unique for the cluster
        project = self._projects.get(project_name)
        if project is None:
            try:
                logging.debug("Searching for project: %s" % project_name)
                project = self._get_next_results(gl, project_name, metric.repo_url, 0)
                if project:
                    logging.debug("Setting project to %s : %s" % (project.name, str(project.id)))
                    self._projects[project_name] = project
            except Exception:
                logging.error("Failed to find project: %s, repo: %s for build %s" % (
                    metric.repo_url, project_name, metric.build_name), exc_info=True)
                raise

        # Using the project id, get the project
        if project is None:
            raise TypeError("Failed to find repo project: %s, for build %s" % (metric.repo_url, metric.build_name))
        try:
            # get the commit from the project using the hash
            short_hash = metric.commit_hash[:8]
            commit = project.commits.get(short_hash)
            # get the commit date/time
            metric.commit_time = commit.committed_date
            # set the timestamp after conversion
            metric.commit_timestamp = pelorus.convert_date_time_to_timestamp(metric.commit_time, self._timedate_format)
        except Exception:
            logging.error("Failed processing commit time for build %s" % metric.build_name, exc_info=True)
            raise
        return metric

    @staticmethod
    def _get_next_results(gl, project_name, git_url, page):
        """
        Returns a list of projects according to the search term project_name.
        :param gl: Gitlab library
        :param project_name: search term in the form of a string
        :param git_url: Repository url stored in the metric
        :param page: int represents the next page to retrieve
        :return: matching project or None if no match is found
        """
        project_list = gl.search(gitlab.SEARCH_SCOPE_PROJECTS, project_name, page=page)
        if project_list:
            project = GitLabCommitCollector.get_matched_project(project_list, git_url)
            if project:
                return gl.projects.get(project['id'])
            else:
                return GitLabCommitCollector._get_next_results(gl, project_name, git_url, page + 1)
        return None

    @staticmethod
    def get_matched_project(project_list, git_url):
        """
        Returns the project in the project list that matches the git url
        :param project_list: list of projects returned by the search by name API call
        :param git_url: Repository url stored in the metric
        :return: Matching project or None if there is no match
        """
        for p in project_list:
            if p.get('http_url_to_repo') == git_url or p.get('ssh_url_to_repo') == git_url:
                return p
        return None

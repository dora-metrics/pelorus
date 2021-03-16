import gitea_client
import requests
import logging
import pelorus
from collector_base import AbstractCommitCollector
# import urllib3
# urllib3.disable_warnings()


class GiteaCommitCollector(AbstractCommitCollector):

    _prefix_pattern = "https://%s/repos/"
    _defaultapi = "try.gitea.io/api/v1"
    _prefix = _prefix_pattern % _defaultapi
    _suffix = "/git/commits/"

    def __init__(self, kube_client, username, token, namespaces, apps, git_api=None):
        super().__init__(kube_client, username, token, namespaces, apps, "Gitea", '%Y-%m-%dT%H:%M:%S', git_api)
        if git_api is not None and len(git_api) > 0:
            logging.info("Using non-default API: %s" % (git_api))
        else:
            self._git_api = self._defaultapi
        self._prefix = self._prefix_pattern % self._git_api

    # base class impl
    def get_commit_time(self, metric):
        """Method called to collect data and send to Prometheus"""
        session = requests.Session()
        session.verify = False

        project_name = metric.repo_project
        git_server = metric.git_server

        if "github" in git_server or "bitbucket" in git_server or "gitlab" in git_server:
            logging.warn("Skipping non Gitea server, found %s" % (git_server))
            return None

        # Private or personal token
        gitea_token = gitea_client.Token(self._token)

        print("token: {}".format(gitea_token))
        # oauth token authentication
        # gs = gitlab.Gitlab(git_server, oauth_token='my_long_token_here', api_version=4, session=session)

        url = self._prefix + metric.repo_group + "/" + metric.repo_project + self._suffix + metric.commit_hash
        logging.info("URL %s" % (url))
        response = requests.get(url, auth=(self._username, self._token))
        logging.info("response %s" % (requests.get(url, auth=(self._username, self._token))))
        if response.status_code != 200:
            # This will occur when trying to make an API call to non-Github
            logging.warning("Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s" % (
                metric.build_name, metric.commit_hash, metric.repo_url, str(response.status_code)))
        else:
            commit = response.json()
            try:
                metric.commit_time = commit['commit']['committer']['date']
                logging.info("metric.commit_time %s" % (str(metric.commit_time)[:19]))
                logging.info("self._timedate_format %s" % (self._timedate_format))
                metric.commit_timestamp = pelorus.convert_date_time_to_timestamp((str(metric.commit_time)[:19]), self._timedate_format)
            except Exception:
                logging.error("Failed processing commit time for build %s" % metric.build_name, exc_info=True)
                logging.debug(commit)
                raise
        return metric

    @staticmethod
    def _get_next_results(gs, project_name, git_url, page):
        """
        Returns a list of projects according to the search term project_name.
        :param gs: Gitlab library
        :param project_name: search term in the form of a string
        :param git_url: Repository url stored in the metric
        :param page: int represents the next page to retrieve
        :return: matching project or None if no match is found
        """
        if page == 0:
            project_list = gs.search('projects', project_name)
        else:
            project_list = gs.search('projects', project_name, page=page)
        if project_list:
            project = GiteaCommitCollector.get_matched_project(project_list, git_url)
            if project:
                return gs.projects.get(project['id'])
            else:
                GiteaCommitCollector._get_next_results(gs, project_name, git_url, page + 1)
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

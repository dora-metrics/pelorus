from collector_base import AbstractCommitCollector
import logging
import pelorus
import requests


class GitHubCommitCollector(AbstractCommitCollector):
    _prefix_pattern = "https://%s/repos/"
    _defaultapi = "api.github.com"
    _prefix = _prefix_pattern % _defaultapi
    _suffix = "/commits/"

    def __init__(self, username, token, namespaces, apps, git_api=None):
        super().__init__(username, token, namespaces, apps, "GitHub", '%Y-%m-%dT%H:%M:%SZ', git_api)
        if self._git_api is not None and len(self._git_api) > 0:
            logging.info("Using non-default API: %s" % (self._git_api))
        else:
            self._git_api = self._defaultapi
        self._prefix = self._prefix_pattern % self._git_api

    def get_commit_time(self, metric):
        """Method called to collect data and send to Prometheus"""
        myurl = metric.repo_url
        url_tokens = myurl.split("/")

        git_server = url_tokens[2]
        # check for gitlab or bitbucket
        if "gitlab" in git_server or "bitbucket" in git_server:
            logging.warn("Skipping non GitHub server, found %s" % (git_server))
            return None

        url = self._prefix + url_tokens[3] + "/" + url_tokens[4].split(".")[0] + self._suffix + metric.commit_hash
        response = requests.get(url, auth=(self._username, self._token))
        if response.status_code != 200:
            # This will occur when trying to make an API call to non-Github
            logging.warning("Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s" % (
                metric.build_name, metric.commit_hash, url_tokens[2], str(response.status_code)))
        else:
            commit = response.json()
            try:
                metric.commit_time = commit['commit']['committer']['date']
                metric.commit_timestamp = pelorus.convert_date_time_to_timestamp(
                    metric.commit_time, self._timedate_format)
            except Exception:
                logging.error("Failed processing commit time for build %s" % metric.build_name, exc_info=True)
                logging.debug(commit)
                raise
        return metric

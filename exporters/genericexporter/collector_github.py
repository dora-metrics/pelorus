from collector_base import AbstractCommitCollector
import logging
import pelorus
import requests
import json


class GitHubCommitCollector(AbstractCommitCollector):
    _prefix_pattern = "https://%s/repos/"
    _defaultapi = "api.github.com"
    _prefix = _prefix_pattern % _defaultapi
    _suffix = "/commits/"

    def __init__(self, username, token, mongo_client, git_api=None):
        super().__init__(username, token, "GitHub", '%Y-%m-%dT%H:%M:%SZ', mongo_client, git_api)
        if git_api is not None and len(git_api) > 0:
            logging.info("Using non-default API: %s" % (git_api))
        else:
            self._git_api = self._defaultapi
        self._prefix = self._prefix_pattern % self._git_api

    def get_commit_time(self, metric):
        """Method called to collect data and send to Prometheus"""
        logging.debug("Metric Value from get_metric_from_build: %s" % (metric.__dict__))
        git_server = metric.git_fqdn
        logging.debug("Git server value: %s" % (git_server))
        # check for gitlab or bitbucket
        if "gitlab" in git_server or "bitbucket" in git_server:
            logging.warn("Skipping non GitHub server, found %s" % (git_server))
            return None

        url = self._prefix + metric.repo_group + "/" + metric.repo_project + self._suffix + metric.commit_hash
        response = requests.get(url, auth=(self._username, self._token))
        if response.status_code != 200:
            # This will occur when trying to make an API call to non-Github
            logging.warning("Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s" % (
                metric.build_name, metric.commit_hash, metric.repo_fqdn, str(response.status_code)))
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

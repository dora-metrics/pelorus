import logging

import requests

import pelorus

from .collector_base import AbstractCommitCollector

# import urllib3
# urllib3.disable_warnings()


class GiteaCommitCollector(AbstractCommitCollector):

    _prefix_pattern = "%s/api/v1/repos/"
    _defaultapi = "try.gitea.io/api/v1"
    _prefix = _prefix_pattern % _defaultapi
    _suffix = "/git/commits/"

    def __init__(self, kube_client, username, token, namespaces, apps, git_api=None):
        super().__init__(
            kube_client,
            username,
            token,
            namespaces,
            apps,
            "Gitea",
            "%Y-%m-%dT%H:%M:%S",
            git_api,
        )
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

        git_server = metric.git_server

        if (
            "github" in git_server
            or "bitbucket" in git_server
            or "gitlab" in git_server
            or "azure" in git_server
        ):
            logging.warn("Skipping non Gitea server, found %s" % (git_server))
            return None

        url = (
            self._prefix
            + metric.repo_group
            + "/"
            + metric.repo_project
            + self._suffix
            + metric.commit_hash
        )
        logging.info("URL %s" % (url))
        response = requests.get(url, auth=(self._username, self._token))
        logging.info(
            "response %s" % (requests.get(url, auth=(self._username, self._token)))
        )
        if response.status_code != 200:
            # This will occur when trying to make an API call to non-Github
            logging.warning(
                "Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s"
                % (
                    metric.build_name,
                    metric.commit_hash,
                    metric.repo_url,
                    str(response.status_code),
                )
            )
        else:
            commit = response.json()
            try:
                metric.commit_time = commit["commit"]["committer"]["date"]
                logging.debug("metric.commit_time %s" % (str(metric.commit_time)[:19]))
                logging.debug("self._timedate_format %s" % (self._timedate_format))
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

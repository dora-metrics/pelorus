import logging
from typing import Optional

import requests
from committime import CommitMetric

import pelorus

from .collector_base import AbstractCommitCollector


class GitHubCommitCollector(AbstractCommitCollector):
    _prefix_pattern = "https://%s/repos/"
    _defaultapi = "api.github.com"
    _prefix = _prefix_pattern % _defaultapi
    _suffix = "/commits/"

    def __init__(
        self,
        kube_client,
        username: Optional[str],
        token: Optional[str],
        namespaces,
        apps,
        git_api=None,
        tls_verify=None,
    ):
        super().__init__(
            kube_client,
            username,
            token,
            namespaces,
            apps,
            "GitHub",
            "%Y-%m-%dT%H:%M:%SZ",
            git_api,
            tls_verify,
        )
        if git_api is not None and len(git_api) > 0:
            logging.info("Using non-default API: %s" % (git_api))
        else:
            self._git_api = self._defaultapi
        self._prefix = self._prefix_pattern % self._git_api

    def get_commit_time(self, metric: CommitMetric):
        """Method called to collect data and send to Prometheus"""
        git_server = metric.git_fqdn
        # check for gitlab or bitbucket
        if "gitlab" in git_server or "bitbucket" in git_server:
            logging.warn("Skipping non GitHub server, found %s" % (git_server))
            return None

        url = (
            self._prefix
            + metric.repo_group
            + "/"
            + metric.repo_project
            + self._suffix
            + metric.commit_hash
        )
        auth = (self._username, self._token) if self._username and self._token else None
        response = requests.get(url, auth=auth, verify=self._tls_verify)
        if response.status_code != 200:
            try:
                message = response.json()["message"]
                logging.warning(
                    "Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s, message %s",
                    metric.build_name,
                    metric.commit_hash,
                    metric.git_fqdn,
                    response.status_code,
                    message,
                )
            except KeyError:
                logging.warning(
                    "Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s",
                    metric.build_name,
                    metric.commit_hash,
                    metric.git_fqdn,
                    response.status_code,
                )
        else:
            commit = response.json()
            try:
                metric.commit_time = commit["commit"]["committer"]["date"]
                metric.commit_timestamp = pelorus.convert_date_time_to_timestamp(
                    metric.commit_time, self._timedate_format
                )
            except Exception:
                logging.error(
                    "Failed processing commit time for build %s" % metric.build_name,
                    exc_info=True,
                )
                logging.debug(commit)
                raise
        return metric

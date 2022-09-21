import logging
from typing import Optional

import requests

from pelorus.certificates import set_up_requests_certs
from provider_common.github import parse_datetime

from .collector_base import AbstractCommitCollector, UnsupportedGITProvider


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

        self.session = requests.Session()
        self.session.verify = set_up_requests_certs(tls_verify)

    def get_commit_time(self, metric):
        """Method called to collect data and send to Prometheus"""
        git_server = metric.git_fqdn
        # check for gitlab or bitbucket
        if (
            "gitea" in git_server
            or "gitlab" in git_server
            or "bitbucket" in git_server
            or "azure" in git_server
        ):
            raise UnsupportedGITProvider(
                "Skipping non GitHub server, found %s" % (git_server)
            )

        url = (
            self._prefix
            + metric.repo_group
            + "/"
            + metric.repo_project
            + self._suffix
            + metric.commit_hash
        )
        auth = (self._username, self._token) if self._username and self._token else None
        response = self.session.get(url, auth=auth)
        if response.status_code != 200:
            # This will occur when trying to make an API call to non-Github
            logging.warning(
                "Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s"
                % (
                    metric.build_name,
                    metric.commit_hash,
                    metric.repo_fqdn,
                    str(response.status_code),
                )
            )
        else:
            commit = response.json()
            try:
                metric.commit_time = commit["commit"]["committer"]["date"]
                metric.commit_timestamp = parse_datetime(metric.commit_time).timestamp()
            except Exception:
                logging.error(
                    "Failed processing commit time for build %s" % metric.build_name,
                    exc_info=True,
                )
                logging.debug(commit)
                raise
        return metric

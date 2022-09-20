import logging

import requests

from pelorus.certificates import set_up_requests_certs
from pelorus.timeutil import parse_assuming_utc, second_precision

from .collector_base import AbstractCommitCollector, UnsupportedGITProvider

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


class GiteaCommitCollector(AbstractCommitCollector):

    _prefix_pattern = "%s/api/v1/repos/"
    _defaultapi = "https://try.gitea.io"
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
            _DATETIME_FORMAT,
            git_api,
        )
        if git_api is not None and len(git_api) > 0:
            logging.info("Using non-default API: %s" % (git_api))
        else:
            self._git_api = self._defaultapi
        self._prefix = self._prefix_pattern % self._git_api
        self.session = requests.Session()
        self.session.verify = set_up_requests_certs()

    # base class impl
    def get_commit_time(self, metric):
        """Method called to collect data and send to Prometheus"""

        git_server = metric.git_server

        if (
            "github" in git_server
            or "bitbucket" in git_server
            or "gitlab" in git_server
            or "azure" in git_server
        ):
            raise UnsupportedGITProvider(
                "Skipping non Gitea server, found %s" % (git_server)
            )

        url = (
            self._prefix
            + metric.repo_group
            + "/"
            + metric.repo_project
            + self._suffix
            + metric.commit_hash
        )
        logging.info("URL %s" % (url))
        response = self.session.get(url, auth=(self._username, self._token))
        logging.info("response %s", response)
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
                commit_time_str: str = commit["commit"]["committer"]["date"]
                metric.commit_time = commit_time_str

                commit_time = parse_assuming_utc(
                    commit_time_str, format=_DATETIME_FORMAT
                )
                commit_time = second_precision(commit_time)

                logging.debug("metric.commit_time %s", commit_time)
                metric.commit_timestamp = commit_time.timestamp()
            except Exception:
                logging.error(
                    "Failed processing commit time for build %s" % metric.build_name,
                    exc_info=True,
                )
                logging.debug(commit)
                raise
        return metric

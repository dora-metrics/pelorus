import logging
from typing import Optional, cast

import requests
import requests.exceptions

import pelorus
from committime import CommitMetric
from committime.collector_base import AbstractCommitCollector, UnsupportedGITProvider
from pelorus.certificates import set_up_requests_certs
from pelorus.timeutil import parse_tz_aware


def commit_url(server: str, group: str, project: str, commit: str) -> str:
    "Get the API endpoint for the given commit"
    return pelorus.url_joiner(
        server,
        f"api/2.0/repositories/{group}/{project}/commit/{commit}",
    )


_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


class BitbucketCommitCollector(AbstractCommitCollector):

    # Default http headers needed for API calls
    DEFAULT_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

    def __init__(
        self, kube_client, username: str, token: str, namespaces, apps, tls_verify=True
    ):
        super().__init__(
            kube_client,
            username,
            token,
            namespaces,
            apps,
            "BitBucket",
            _DATETIME_FORMAT,
        )
        self.__session = requests.Session()
        self.__session.verify = set_up_requests_certs(tls_verify)
        self.__session.headers.update(self.DEFAULT_HEADERS)
        if self._username and self._token:
            self.__session.auth = (self._username, self._token)

    def get_commit_time(self, metric: CommitMetric):
        git_server = metric.git_server

        # do a simple check for hosted Git services.
        if (
            "github" in git_server
            or "gitea" in git_server
            or "gitlab" in git_server
            or "azure" in git_server
        ):
            raise UnsupportedGITProvider(
                "Skipping non BitBucket server, found %s" % (git_server)
            )

        try:
            git_server = metric.git_server

            project_name = metric.repo_project
            sha = cast(str, metric.commit_hash)
            group = metric.repo_group

            api_dict = self.get_commit_information(
                git_server, group, project_name, sha, metric
            )

            if api_dict is None:
                return metric

            commit_time = api_dict["date"]
            logging.debug("API v2 returned sha: %s, commit date: %s", sha, commit_time)
            metric.commit_time = commit_time
            metric.commit_timestamp = parse_tz_aware(
                metric.commit_time, format=_DATETIME_FORMAT
            ).timestamp()
        except requests.exceptions.SSLError as e:
            logging.error(
                "TLS error talking to %s for build %s: %s",
                git_server,
                metric.build_name,
                e,
            )
        except Exception:
            logging.error(
                "Failed processing commit time for build %s",
                metric.build_name,
                exc_info=True,
            )
            raise
        return metric

    def get_commit_information(
        self,
        git_server: str,
        group: str,
        project_name: str,
        sha: str,
        metric: CommitMetric,
    ) -> Optional[dict]:
        """
        Call the bitbucket API to get commit information.

        Returns None if any of the following occur:
        - the response status code was not a success
        - the response body was not valid JSON
        - the response body was JSON, but not a dictionary

        Returns the JSON body otherwise.

        You may assume all of these cases have already been logged.
        """
        api_response = None
        try:
            url = commit_url(git_server, group, project_name, sha)

            response = self.__session.get(url)
            response.encoding = "utf-8"
            response.raise_for_status()

            json_body = response.json()

            if not isinstance(json_body, dict):
                raise requests.exceptions.JSONDecodeError

            logging.debug(
                (
                    "For project %(project)s, repo %(repo)s, build %(build)s, "
                    "commit %(commit)s BitBucket returned %(response)s"
                ),
                dict(
                    project=project_name,
                    repo=metric.repo_url,
                    build=metric.build_name,
                    commit=metric.commit_hash,
                    response=response.text,
                ),
            )

            return json_body
        except requests.HTTPError as e:
            logging.error(
                (
                    "HTTP Error while searching for project %(project)s, repo %(repo)s, build %(build)s, "
                    "commit %(commit)s: %(http_err)s"
                ),
                dict(
                    project=project_name,
                    repo=metric.repo_url,
                    build=metric.build_name,
                    commit=metric.commit_hash,
                    http_err=e,
                ),
            )
        except requests.exceptions.JSONDecodeError as e:
            logging.error(
                (
                    "Response for project %(project)s, repo %(repo)s, build %(build)s, "
                    "commit %(commit)s was not valid JSON: %(json_err)s"
                ),
                dict(
                    project=project_name,
                    repo=metric.repo_url,
                    build=metric.build_name,
                    commit=metric.commit_hash,
                    json_err=e,
                ),
            )
        return api_response

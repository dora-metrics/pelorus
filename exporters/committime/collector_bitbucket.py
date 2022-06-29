import enum
import logging
from typing import Optional, cast

import requests
import requests.exceptions

import pelorus
from committime import CommitMetric
from committime.collector_base import AbstractCommitCollector


class ApiVersion(enum.Enum):
    """Known versions of the Bitbucket API."""

    root: str
    test: str
    pattern: str

    def __init__(self, root, test, pattern):
        self.root = root
        self.test = test
        self.pattern = pattern

    V_2_0 = (
        "api",
        "2.0/repositories",
        "2.0/repositories/{group}/{project}/commit/{commit}",
    )

    V_1_0 = (
        "rest/api",
        "1.0/projects",
        "1.0/projects/{group}/repos/{project}/commits/{commit}",
    )

    def commit_url(self, server: str, group: str, project: str, commit: str) -> str:
        return pelorus.url_joiner(
            server,
            self.root,
            self.pattern.format(group=group, project=project, commit=commit),
        )

    def test_url(self, server: str) -> str:
        return pelorus.url_joiner(server, self.root, self.test)


class BitbucketCommitCollector(AbstractCommitCollector):

    # Default http headers needed for API calls
    DEFAULT_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

    def __init__(self, kube_client, username, token, namespaces, apps, tls_verify=True):
        super().__init__(
            kube_client,
            username,
            token,
            namespaces,
            apps,
            "BitBucket",
            "%Y-%m-%dT%H:%M:%S%z",
        )
        self.__cached_server_api_versions: dict[str, ApiVersion] = {}
        self.__session = requests.Session()
        self.__session.verify = tls_verify
        self.__session.headers.update(self.DEFAULT_HEADERS)
        self.__session.auth = (self._username, self._token)

    def get_commit_time(self, metric: CommitMetric):
        git_server = metric.git_server

        # do a simple check for hosted Git services.
        if "github" in git_server or "gitlab" in git_server:
            logging.warn("Skipping non BitBucket server, found %s" % (git_server))
            return None

        try:
            # Get or figure out the BB API version
            # check the cache
            api_version = self.get_api_version(git_server)
            if api_version is None:
                return metric

            if api_version is ApiVersion.V_1_0:
                metric = self.get_commit_time_v1(metric)
            elif api_version is ApiVersion.V_2_0:
                metric = self.get_commit_time_v2(metric)
            else:
                raise RuntimeError(f"unknown API Version {api_version}")
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

    def get_commit_time_v1(self, metric: CommitMetric) -> CommitMetric:
        """
        Get commit time information from the V1 version of the API.
        """
        git_server = metric.git_server

        project_name = metric.repo_project
        sha = metric.commit_hash
        group = metric.repo_group

        # URL munging copied from original code.
        # TODO: this is messy. We should investigate the parsing that CommitMetric is doing.

        # Due to the BB V1 git pattern differences, need remove '/scm' and parse again.
        old_url = metric.repo_url
        # Parse out the V1 /scm, for whatever reason why it is present.
        new_url = old_url.replace("/scm", "")
        # set the new url, so the parsing will happen
        metric.repo_url = new_url
        # set the new project name
        project_name = metric.repo_project
        # set the new group
        group = metric.repo_group
        # set the URL back to the original
        metric.repo_url = old_url

        api_dict = self.get_commit_information(
            git_server, ApiVersion.V_1_0, group, project_name, sha, metric
        )

        if api_dict is None:
            return metric

        # API V1 has the commit timestamp, which does not need to be converted
        commit_timestamp = api_dict["committerTimestamp"]
        logging.debug("API v1 returned sha: %s, timestamp: %s", sha, commit_timestamp)
        # Convert timestamp from miliseconds to seconds
        converted_timestamp = commit_timestamp / 1000
        # set the timestamp in the metric
        metric.commit_timestamp = converted_timestamp
        # convert the time stamp to datetime and set in metric
        metric.commit_time = pelorus.convert_timestamp_to_date_time_str(
            converted_timestamp
        )

        return metric

    def get_commit_time_v2(self, metric: CommitMetric) -> CommitMetric:
        """
        Get commit time information from the V2 version of the API.
        """
        git_server = metric.git_server

        project_name = metric.repo_project
        sha = metric.commit_hash
        group = metric.repo_group

        api_dict = self.get_commit_information(
            git_server, ApiVersion.V_2_0, group, project_name, sha, metric
        )

        if api_dict is None:
            return metric

        # API V2 only has the commit time, which needs to be converted.
        # get the commit date/time
        commit_time = api_dict["date"]
        logging.debug("API v2 returned sha: %s, commit date: %s", sha, commit_time)
        # set the commit time from the API
        metric.commit_time = commit_time
        # set the timestamp after conversion
        metric.commit_timestamp = pelorus.convert_date_time_to_timestamp(
            metric.commit_time, self._timedate_format
        )

        return metric

    def get_commit_information(
        self,
        git_server: str,
        api_version: ApiVersion,
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
            url = api_version.commit_url(git_server, group, project_name, sha)

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

    def get_api_version(self, git_server: str) -> Optional[ApiVersion]:
        """
        Get the API version for the server from the cache.
        If absent, test API urls to see which version is correct.
        """
        api_version = self.__cached_server_api_versions.get(git_server)

        if api_version is not None:
            return api_version

        try:
            for potential_api_version in ApiVersion:
                if self.check_api_verison(git_server, potential_api_version):
                    api_version = self.__cached_server_api_versions[
                        git_server
                    ] = potential_api_version
                    break
        except requests.HTTPError as e:
            logging.error(
                "While testing for API Version %s at server %s, got response: %s",
                cast(ApiVersion, potential_api_version)._name_,
                git_server,
                e,
            )

        return api_version

    def check_api_verison(self, git_server: str, api_version: ApiVersion) -> bool:
        """
        Check if the git_server supports a given ApiVersion.
        Will return True if so, False if there's some non-successful response,
        or re-raise the requests.HTTPError if the response was 401 UNAUTHORIZED
        """
        url = api_version.test_url(git_server)

        response = self.__session.get(url)
        try:
            response.raise_for_status()
            return True
        except requests.HTTPError as e:
            status = e.response.status_code

            if status == requests.codes.unauthorized:
                raise

            logging.warning(
                "While testing API version at URL %s got response: %s",
                url,
                status,
            )
            return False

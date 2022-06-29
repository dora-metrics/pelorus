import enum
import logging
from typing import Optional

import requests
import requests.exceptions

import pelorus
from committime import CommitMetric
from committime.collector_base import AbstractCommitCollector


class ApiVersion(enum.Enum):
    """Known versions of the Bitbucket API."""

    V_1_0 = "1.0"
    V_2_0 = "2.0"


class BitbucketCommitCollector(AbstractCommitCollector):

    # globals for Bitbucket v1 API
    V1_API_ROOT = "rest/api"
    V1_API_TEST = "1.0/projects"
    V1_API_PATTERN = "1.0/projects/{group}/repos/{project}/commits/{commit}"
    # globals for Bitbucket v2 API
    V2_API_ROOT = "api"
    V2_API_TEST = "2.0/repositories"
    V2_API_PATTERN = "2.0/repositories/{group}/{project}/commit/{commit}"
    # Default http headers needed for API calls
    DEFAULT_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

    def __init__(self, kube_client, username, token, namespaces, apps):
        super().__init__(
            kube_client,
            username,
            token,
            namespaces,
            apps,
            "BitBucket",
            "%Y-%m-%dT%H:%M:%S%z",
        )
        self.__server_dict: dict[str, ApiVersion] = {}
        self.__session = requests.Session()

    # base class impl
    def get_commit_time(self, metric: CommitMetric):
        """Method called to collect data and send to Prometheus"""

        git_server = metric.git_server
        # do a simple check for hosted Git services.
        if "github" in git_server or "gitlab" in git_server:
            logging.warn("Skipping non BitBucket server, found %s" % (git_server))
            return None

        # Set the session auth
        self.__session.auth = (self._username, self._token)

        try:
            # Get or figure out the BB API version
            # check the cache
            api_version = self.get_api_version(git_server)
            if api_version is None:
                return metric

            # get the project, group, and commit sha properties from the existing metric
            project_name = metric.repo_project
            sha = metric.commit_hash
            group = metric.repo_group

            # set API variables depending on the version
            if api_version == ApiVersion.V_1_0:
                # start with the V1 globals
                api_root = self.V1_API_ROOT
                api_pattern = self.V1_API_PATTERN
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
            elif api_version == ApiVersion.V_2_0:
                # Just set the V2 globals
                api_root = self.V2_API_ROOT
                api_pattern = self.V2_API_PATTERN
            else:
                raise RuntimeError(f"unknown API Version {api_version}")

            # Create the API server from the Git server and API Root
            api_server = pelorus.url_joiner(git_server, api_root)

            api_j = self.get_commit_information(
                api_pattern, api_server, group, project_name, sha, metric
            )

            if api_j is None:
                return metric

            if api_version == ApiVersion.V_2_0:
                # API V2 only has the commit time, which needs to be converted.
                # get the commit date/time
                commit_time = api_j["date"]
                logging.debug(
                    "API v2 returned sha: %s, commit date: %s" % (sha, str(commit_time))
                )
                # set the commit time from the API
                metric.commit_time = commit_time
                # set the timestamp after conversion
                metric.commit_timestamp = pelorus.convert_date_time_to_timestamp(
                    metric.commit_time, self._timedate_format
                )
            elif api_version == ApiVersion.V_1_0:
                # API V1 has the commit timestamp, which does not need to be converted
                commit_timestamp = api_j["committerTimestamp"]
                logging.debug(
                    "API v1 returned sha: %s, timestamp: %s"
                    % (sha, str(commit_timestamp))
                )
                # Convert timestamp from miliseconds to seconds
                converted_timestamp = commit_timestamp / 1000
                # set the timestamp in the metric
                metric.commit_timestamp = converted_timestamp
                # convert the time stamp to datetime and set in metric
                metric.commit_time = pelorus.convert_timestamp_to_date_time_str(
                    converted_timestamp
                )
            else:
                raise RuntimeError(f"unknown API Version {api_version}")
        except Exception:
            logging.error(
                "Failed processing commit time for build %s" % metric.build_name,
                exc_info=True,
            )
            raise
        return metric

    def get_commit_information(
        self,
        api_pattern: str,
        api_server: str,
        group: str,
        project_name: str,
        sha: str,
        metric: CommitMetric,
    ) -> Optional[dict]:
        """
        Call the bitbucket API to get commit information.

        Returns None if any of the following occur:
        - there was an exception,
        - the response status code was not a success
        - the response body was not valid JSON
        - the response body was JSON, but not a dictionary

        Returns the JSON body otherwise.

        You may assume all of these cases have already been logged.
        """
        api_response = None
        try:
            path = api_pattern.format(group=group, project=project_name, commit=sha)
            url = pelorus.url_joiner(api_server, path)

            response = self.__session.request(
                "GET", url=url, headers=self.DEFAULT_HEADERS
            )
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
        except Exception:
            logging.warning(
                "Failed to find project: %s, repo: %s for build %s"
                % (metric.repo_url, project_name, metric.build_name),
                exc_info=True,
            )
        return api_response

    def get_api_version(self, git_server: str) -> Optional[ApiVersion]:
        """Checks the map for a the Git server API version.  If not found it makes an API call to determine."""
        api_version = self.__server_dict.get(git_server)

        if api_version is not None:
            return api_version

        if self.check_api_verison(git_server, self.V2_API_ROOT, self.V2_API_TEST):
            api_version = self.__server_dict[git_server] = ApiVersion.V_2_0
        elif self.check_api_verison(git_server, self.V1_API_ROOT, self.V1_API_TEST):
            api_version = self.__server_dict[git_server] = ApiVersion.V_1_0

        return api_version

    def check_api_verison(self, git_server: str, api_root: str, api_test: str) -> bool:
        """Makes an API call to determine the API version"""
        api_server = pelorus.url_joiner(git_server, api_root)
        url = pelorus.url_joiner(api_server, api_test)

        response = self.__session.request("GET", url=url, headers=self.DEFAULT_HEADERS)
        status_code = response.status_code

        if status_code == 200:
            return True
        else:
            logging.warning(
                "While testing API version at URL %s got response: %s",
                url,
                status_code,
            )
            return False

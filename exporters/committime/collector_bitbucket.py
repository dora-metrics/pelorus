import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import giturlparse
import requests
import requests.exceptions
from attrs import define, field

import pelorus
from committime import CommitMetric
from committime.collector_base import AbstractCommitCollector, check_provider_support
from pelorus.timeutil import parse_tz_aware
from pelorus.utils import set_up_requests_session


class APIVersion(ABC):
    "Handle API-version dependent behavior."

    @abstractmethod
    def test_url(self, server: str) -> str:
        "The URL used to test if the server implements this API version."
        ...

    @abstractmethod
    def commit_url(self, metric: CommitMetric) -> str:
        "Get the API URL for the given commit"
        ...

    @abstractmethod
    def update_metric_from_api(self, metric: CommitMetric, api_response: dict):
        "Update the metric's timestamp info from the API response."
        ...

    def __str__(self):
        return type(self).__name__


class Version1(APIVersion):
    root = "rest/api"
    pattern = "1.0/projects/{group}/repos/{project}/commits/{commit}"
    test_path = "1.0/projects"

    def test_url(self, server: str) -> str:
        return pelorus.url_joiner(server, self.root, self.test_path)

    def commit_url(self, metric: CommitMetric) -> str:
        "Handle the URL for v1 specially."

        git_server = metric.git_server
        sha = metric.commit_hash

        # Extract project/group by parsing the URL with '/scm' removed,
        # without mutating metric.repo_url (which triggers expensive re-parsing).
        url_without_scm = metric.repo_url.replace("/scm", "")
        parsed = giturlparse.parse(url_without_scm)
        project_name = parsed.name
        group = parsed.owner

        return pelorus.url_joiner(
            git_server,
            self.root,
            self.pattern.format(group=group, project=project_name, commit=sha),
        )

    def update_metric_from_api(self, metric: CommitMetric, api_response: dict):
        # API V1 uses unix time
        commit_timestamp = api_response.get("committerTimestamp")
        if commit_timestamp is None:
            raise KeyError(
                f"Bitbucket API v1 response missing 'committerTimestamp' for commit {metric.commit_hash}"
            )

        # Convert timestamp from milliseconds to seconds
        converted_timestamp = commit_timestamp / 1000

        timestamp = datetime.fromtimestamp(converted_timestamp, tz=timezone.utc)

        logging.debug(
            "API v1 returned sha: %s, timestamp: %s (%s)",
            metric.commit_hash,
            timestamp,
            converted_timestamp,
        )
        metric.commit_timestamp = converted_timestamp
        metric.commit_time = timestamp.isoformat()
        metric.commit_link = "unknown"


class Version2(APIVersion):
    root = "api"
    pattern = "2.0/repositories/{group}/{project}/commit/{commit}"
    test_path = "2.0/repositories"

    def test_url(self, server: str) -> str:
        return pelorus.url_joiner(server, self.root, self.test_path)

    def commit_url(self, metric: CommitMetric) -> str:
        server = metric.git_server

        project = metric.repo_project
        commit = metric.commit_hash
        group = metric.repo_group

        return pelorus.url_joiner(
            server,
            self.root,
            self.pattern.format(group=group, project=project, commit=commit),
        )

    def update_metric_from_api(self, metric: CommitMetric, api_response: dict):
        commit_time = api_response.get("date")
        if commit_time is None:
            raise KeyError(
                f"Bitbucket API v2 response missing 'date' for commit {metric.commit_hash}"
            )
        timestamp = parse_tz_aware(commit_time, _DATETIME_FORMAT)
        html_link = api_response.get("links", {}).get("html", {})
        commit_link = html_link.get("href", "unknown") if isinstance(html_link, dict) else "unknown"

        logging.debug(
            "API v2 returned sha: %s, timestamp: %s (%s)",
            metric.commit_hash,
            timestamp,
            commit_time,
        )
        metric.commit_time = commit_time
        metric.commit_timestamp = timestamp.timestamp()
        metric.commit_link = commit_link


_SUPPORTED_API_VERSIONS = (Version2(), Version1())

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


@define(kw_only=True)
class BitbucketCommitCollector(AbstractCommitCollector):
    # Default http headers needed for API calls
    DEFAULT_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

    cached_server_api_versions: dict[str, APIVersion] = field(factory=dict, init=False)

    session: requests.Session = field(factory=requests.Session, init=False)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        set_up_requests_session(
            self.session, self.tls_verify, username=self.username, token=self.token
        )
        self.session.headers.update(self.DEFAULT_HEADERS)

    def get_commit_time(self, metric: CommitMetric):
        git_server = metric.git_server

        check_provider_support(git_server, "bitbucket")

        try:
            api_version = self.get_api_version(git_server)
            if api_version is None:
                return metric

            api_dict = self.get_commit_information(api_version, metric)

            if api_dict is None:
                return metric

            api_version.update_metric_from_api(metric, api_dict)

            return metric
        except requests.exceptions.SSLError:
            logging.error(
                "TLS error talking to %s for build %s",
                git_server,
                metric.build_name,
                exc_info=True,
            )
            raise
        except Exception:
            logging.error(
                "Failed processing commit time for build %s",
                metric.build_name,
                exc_info=True,
            )
            raise

    def get_commit_information(
        self,
        api_version: APIVersion,
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
        try:
            url = api_version.commit_url(metric)

            response = self.session.get(url, timeout=30)
            response.encoding = "utf-8"
            response.raise_for_status()

            json_body = response.json()

            if not isinstance(json_body, dict):
                logging.error(
                    "Bitbucket API returned non-object JSON for build %s",
                    metric.build_name,
                )
                return None

            logging.debug(
                (
                    "For project %(project)s, repo %(repo)s, build %(build)s, "
                    "commit %(commit)s BitBucket returned status %(status)s"
                ),
                dict(
                    project=metric.repo_name,
                    repo=metric.repo_url,
                    build=metric.build_name,
                    commit=metric.commit_hash,
                    status=response.status_code,
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
                    project=metric.repo_name,
                    repo=metric.repo_url,
                    build=metric.build_name,
                    commit=metric.commit_hash,
                    http_err=e,
                ),
                exc_info=True,
            )
        except requests.exceptions.JSONDecodeError as e:
            logging.error(
                (
                    "Response for project %(project)s, repo %(repo)s, build %(build)s, "
                    "commit %(commit)s was not valid JSON: %(json_err)s"
                ),
                dict(
                    project=metric.repo_name,
                    repo=metric.repo_url,
                    build=metric.build_name,
                    commit=metric.commit_hash,
                    json_err=e,
                ),
                exc_info=True,
            )
        return None

    def get_api_version(self, server: str) -> Optional[APIVersion]:
        """
        Get the API version for the server from the cache.
        If absent, test API urls to see which version is correct,
        updating the cache.
        """
        api_version = self.cached_server_api_versions.get(server)

        if api_version is not None:
            return api_version

        for potential_api_version in _SUPPORTED_API_VERSIONS:
            if self.check_api_version(server, potential_api_version):
                api_version = potential_api_version
                self.cached_server_api_versions[server] = potential_api_version
                break

        if api_version is None:
            logging.warning("No matching API version for server %s", server)

        return api_version

    def check_api_version(self, git_server: str, api_version: APIVersion) -> bool:
        """
        Check if the git_server supports a given ApiVersion.
        Will return True if so, False if there's some non-successful response.
        Non-successes will be logged.
        """
        url = api_version.test_url(git_server)

        response = self.session.get(url, timeout=30)
        try:
            response.raise_for_status()
            return True
        except requests.HTTPError as e:
            status = e.response.status_code

            log_method = (
                logging.error
                if status == requests.codes.unauthorized
                else logging.warning
            )

            log_method(
                "While testing API Version %s at url %s, got response: %s",
                api_version,
                url,
                status,
            )
            return False

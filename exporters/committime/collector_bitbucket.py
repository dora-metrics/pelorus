import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import requests
import requests.exceptions
from attrs import define, field

import pelorus
from committime import CommitInfo, GitRepo
from committime.collector_base import AbstractGitCommitCollector, UnsupportedGITProvider
from pelorus.timeutil import parse_tz_aware
from pelorus.utils import set_up_requests_session


class APIVersion(ABC):
    "Handle API-version dependent behavior."

    @abstractmethod
    def test_url(self, server: str) -> str:
        "The URL used to test if the server implements this API version."
        ...

    @abstractmethod
    def commit_url(self, info: CommitInfo) -> str:
        "Get the API URL for the given commit"
        ...

    @abstractmethod
    def timestamp_from_api(self, info: CommitInfo, api_response: dict) -> datetime:
        "Get timestamp from the API response."
        ...

    def __str__(self):
        return type(self).__name__


class Version1(APIVersion):
    root = "rest/api"
    pattern = "1.0/projects/{group}/repos/{project}/commits/{commit}"
    test_path = "1.0/projects"

    def test_url(self, server: str) -> str:
        return pelorus.url_joiner(server, self.root, self.test_path)

    def commit_url(self, info: CommitInfo) -> str:
        "Handle the URL for v1 specially."

        original_repo, sha = info

        git_server = original_repo.server

        # URL munging adapted from older code.

        # Due to the BB V1 git pattern differences, need remove '/scm' and parse again.
        old_url = original_repo.url
        # Parse out the V1 /scm, for whatever reason why it is present.
        new_url = old_url.replace("/scm", "")
        repo = GitRepo.from_url(new_url)

        return pelorus.url_joiner(
            git_server,
            self.root,
            self.pattern.format(group=repo.group, project=repo.project, commit=sha),
        )

    def timestamp_from_api(self, info: CommitInfo, api_response: dict) -> datetime:
        # API V1 uses unix time
        commit_timestamp = api_response["committerTimestamp"]

        # Convert timestamp from miliseconds to seconds
        converted_timestamp = commit_timestamp / 1000

        timestamp = datetime.fromtimestamp(converted_timestamp, tz=timezone.utc)
        return timestamp


class Version2(APIVersion):
    root = "api"
    pattern = "2.0/repositories/{group}/{project}/commit/{commit}"
    test_path = "2.0/repositories"

    def test_url(self, server: str) -> str:
        return pelorus.url_joiner(server, self.root, self.test_path)

    def commit_url(self, info: CommitInfo) -> str:
        repo, commit = info

        return pelorus.url_joiner(
            repo.server,
            self.root,
            self.pattern.format(group=repo.group, project=repo.project, commit=commit),
        )

    def timestamp_from_api(self, info: CommitInfo, api_response: dict) -> datetime:
        # API V2 has a human-readable time, which needs to be parsed.
        commit_time = api_response["date"]
        timestamp = parse_tz_aware(commit_time, _DATETIME_FORMAT)
        return timestamp


_SUPPORTED_API_VERSIONS = (Version2(), Version1())

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


@define(kw_only=True)
class BitbucketCommitCollector(AbstractGitCommitCollector):
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

    def get_commit_time(self, info: CommitInfo):
        git_server = info.repo.server

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
            api_version = self.get_api_version(git_server)
            if api_version is None:
                return None

            api_dict = self.get_commit_information(api_version, info)

            if api_dict is None:
                return None

            return api_version.timestamp_from_api(info, api_dict)
        except requests.exceptions.SSLError as e:
            logging.error(
                "TLS error talking to %s: %s",
                git_server,
                e,
            )
        except Exception:
            logging.error(
                "Failed processing commit time",
                exc_info=True,
            )
            raise

    def get_commit_information(
        self, api_version: APIVersion, info: CommitInfo
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
            url = api_version.commit_url(info)

            response = self.session.get(url)
            response.encoding = "utf-8"
            response.raise_for_status()

            json_body = response.json()

            if not isinstance(json_body, dict):
                raise requests.exceptions.JSONDecodeError("JSON was not an object")

            logging.debug(
                (
                    "For project %(project)s, repo %(repo)s, "
                    "commit %(commit)s BitBucket returned %(response)s"
                ),
                dict(
                    project=info.repo.name,
                    repo=info.repo.url,
                    commit=info.commit_hash,
                    response=response.text,
                ),
            )

            return json_body
        except requests.HTTPError as e:
            logging.error(
                (
                    "HTTP Error while searching for project %(project)s, repo %(repo)s, "
                    "commit %(commit)s: %(http_err)s"
                ),
                dict(
                    project=info.repo.name,
                    repo=info.repo.url,
                    commit=info.commit_hash,
                    http_err=e,
                ),
            )
        except requests.exceptions.JSONDecodeError as e:
            logging.error(
                (
                    "Response for project %(project)s, repo %(repo)s, "
                    "commit %(commit)s was not valid JSON: %(json_err)s"
                ),
                dict(
                    project=info.repo.name,
                    repo=info.repo_url,
                    commit=info.commit_hash,
                    json_err=e,
                ),
            )
        return api_response

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
            if self.check_api_verison(server, potential_api_version):
                api_version = potential_api_version
                self.cached_server_api_versions[server] = potential_api_version
                break

        if api_version is None:
            logging.warning("No matching API version for server %s", server)

        return api_version

    def check_api_verison(self, git_server: str, api_version: APIVersion) -> bool:
        """
        Check if the git_server supports a given ApiVersion.
        Will return True if so, False if there's some non-successful response.
        Non-successes will be logged.
        """
        url = api_version.test_url(git_server)

        response = self.session.get(url)
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

"""
A metric collector that treats GitHub releases as "deployments".
Meant for internal usage only, at least for now.
"""
from __future__ import annotations

import logging
from datetime import datetime
from functools import partial
from typing import Any, Iterable, NamedTuple, Optional, TypeVar, cast
from urllib.parse import parse_qs

import requests
from attrs import define, field
from prometheus_client.core import GaugeMetricFamily
from urllib3.util import Url

from pelorus import AbstractPelorusExporter
from pelorus.config import REDACT, env_vars, load_and_log, log
from pelorus.config.converters import comma_or_whitespace_separated
from pelorus.utils import CachedData, join_url_path_components
from provider_common.github import GitHubError, paginate_items, parse_datetime
from provider_common.github.errors import GitHubRateLimitError
from provider_common.github.rate_limit import RateLimitingClient


class Release(NamedTuple):
    """
    A tagged release of a GitHub project.
    """

    name: str
    tag_name: str
    published_at: datetime

    @classmethod
    def from_json(cls, json_object: dict[str, Any]) -> Release:
        """
        Create from the JSON object returned by the `/releases` resource.
        """
        name = json_object["name"]
        tag_name = json_object["tag_name"]
        published_at = parse_datetime(json_object["published_at"])

        return Release(name, tag_name, published_at)


class ProjectSpec(NamedTuple):
    """
    A project to look at, as specified from configuration.

    It takes the form of a pseudo-URL: a path with at least two segments,
    and query args used to override defaults.

    Examples: `organization/repo` or `organization/repo?app=app_name`
    """

    organization: str
    repo: str
    app: str

    @staticmethod
    def one_from_env_var(var: str | ProjectSpec):
        if isinstance(var, ProjectSpec):
            return var

        # TODO: compare approaches. The below was from master.
        # url = urllib.parse.urlsplit(var)
        # parts = url.path.split("/")
        path, _, query = var.partition("?")
        parts = path.split("/")

        if len(parts) != 2:
            raise ValueError(
                f"Each project needs to be in `organization/repo[?args]` format. {var} is invalid."
            )

        org, repo = parts

        query_params = parse_qs(query)

        if "app" in query_params:
            app = query_params["app"][0]
        else:
            app = repo

        return ProjectSpec(org, repo, app)

    @staticmethod
    def all_from_env_var(var: str | set[str] | set[ProjectSpec]) -> set[ProjectSpec]:
        return set(
            ProjectSpec.one_from_env_var(x)
            for x in comma_or_whitespace_separated(set)(var)
        )

    def __str__(self):
        return f"{self.organization}/{self.repo}"


CachedReleases = CachedData[set[Release]]
CachedTags = CachedData[dict[str, str]]

T = TypeVar("T")


@define
class GitHubReleaseCollector(AbstractPelorusExporter):
    # TODO: regex to determine which releases are "prod"?

    projects: set[ProjectSpec] = field(converter=ProjectSpec.all_from_env_var)
    # TODO: url converter from other uses
    host: Url = field(default="api.github.com", metadata=env_vars("GIT_API"))
    token: Optional[str] = field(default=None, metadata=log(REDACT))
    tls_verify: bool = field(default=True)  # TODO: compare against other uses

    session: requests.Session = field(factory=requests.Session, init=False)
    _client: RateLimitingClient = field(init=False)

    _project_release_cache: dict[str, CachedReleases] = field(factory=dict, init=False)
    "Maps project names to their `Last-Modified` header and their releases."

    _project_tag_cache: dict[str, CachedTags] = field(factory=dict, init=False)
    "Maps project names to their last-modified header and their tags (by name)."

    def __attrs_post_init__(self):
        if not self.projects:
            raise ValueError("No projects specified for GitHub deploytime collector")

        # TODO: lives in other branch
        # set_up_requests_session(
        #     self.session, auth=TokenAuth(self.token) if self.token else None
        # )

        self._client = RateLimitingClient(self.session)

    def collect(self) -> Iterable[GaugeMetricFamily]:
        metric = GaugeMetricFamily(
            "deploy_timestamp",
            "Deployment timestamp",
            labels=["namespace", "app", "image_sha", "release_tag", "commit_id"],
        )

        for project in self.projects:
            releases = set(self._get_releases_for_project(project))
            logging.debug("Got %d releases for project %s", len(releases), project)

            commits = self._get_each_tag_commit(
                project, set(release.tag_name for release in releases)
            )
            logging.debug("Got %d tagged commits for project %s", len(commits), project)

            namespace, app = project.organization, project.app

            for release in releases:
                if commit := commits.get(release.tag_name):
                    logging.info(
                        "Collected (release) deploy_timestamp{namespace/org=%s, app/repo=%s, image/commit=%s} %s",
                        namespace,
                        app,
                        commit,
                        release.published_at,
                    )
                    metric.add_metric(
                        [namespace, app, commit, release.tag_name, commit],
                        release.published_at.timestamp(),
                        release.published_at.timestamp(),
                    )
                else:
                    logging.error(
                        "Project %s's release %s (tag %s) did not have a matching commit",
                        project,
                        release.name,
                        release.tag_name,
                    )

        yield metric

    def _get_releases_for_project(self, project: ProjectSpec) -> set[Release]:
        """
        Get all releases for a project.

        Will make the request with the cache time if there is a cached response.

        If a rate limit is hit, cached data will be returned if it exists,
        or empty data if not. Both cases will be logged.
        """

        path = join_url_path_components(
            "repos", project.organization, project.repo, "releases"
        )
        url = self.host._replace(path=path)

        cached = self._project_release_cache.get(str(project), None)
        options = dict(headers=cached.if_modified_since) if cached is not None else {}

        releases: set[Release] = set()

        try:
            request = requests.Request("GET", url.url, **options)
            response = self._client.request(request)

            if response.status_code == requests.codes["not modified"]:
                return cast(CachedReleases, cached).data

            last_modified = response.headers.get("Last-Modified")

            for release in paginate_items(self._client, response):
                if not release["draft"]:
                    releases.add(Release.from_json(release))

            if last_modified:
                self._project_release_cache[str(project)] = CachedData(
                    last_modified, releases
                )
        except GitHubRateLimitError:
            # return stale data with the hopes we'll be un-limited soon.
            # The rate limit itself is already logged, but let's inform
            # that this is outdated data.
            if cached and releases:
                logging.info(
                    "Got some info before rate limiting, augmenting with cache"
                )
                releases = cached.data | releases
            elif cached:
                logging.info("Returning cached data since we are rate limited")
                releases = cached.data
            else:
                logging.info("Returning no data because we are rate limited")
        except GitHubError as e:
            logging.error(
                "Error while getting GitHub response for project %s: %s",
                project,
                e,
                exc_info=True,
            )

        return releases

    def _get_each_tag_commit(
        self, project: ProjectSpec, tags: set[str]
    ) -> dict[str, str]:
        """
        Gets the linked commit for every tag given.
        Returns a dictionary where the key is the tag name,
        and the value is the commit hash.

        The tag will not be present in the dict if the tag was not found.

        If one of the following errors occurred, then it will be logged,
        and whatever info that was collected so far will be returned.

        BadAttributePathError if info is missing,
        Any GitHubError from talking to GitHub
        """

        path = join_url_path_components(
            "repos", project.organization, project.repo, "tags"
        )
        url = self.host._replace(path=path)

        cached = self._project_tag_cache.get(str(project), None)
        options = dict(headers=cached.if_modified_since) if cached is not None else {}

        tags_to_commits = {}

        try:
            request = requests.Request("GET", url.url, **options)
            response = self._client.request(request)

            if response.status_code == requests.codes["not modified"]:
                return cast(CachedTags, cached).data

            last_modified = response.headers.get("Last-Modified")

            for tag in paginate_items(self._client, response):
                tag_name = tag["name"]

                if tag_name in tags:
                    tags_to_commits[tag_name] = tag["commit"]["sha"]

            if last_modified:
                self._project_tag_cache[str(project)] = CachedData(
                    last_modified, tags_to_commits
                )
        except GitHubRateLimitError:
            # return stale data with the hopes we'll be un-limited soon.
            # The rate limit itself is already logged, but let's inform
            # that this is outdated data.
            if cached and tags_to_commits:
                logging.info(
                    "Got some info before rate limiting, augmenting with cache"
                )
                tags_to_commits = cached.data | tags_to_commits
            elif cached:
                logging.info("Returning cached data since we are rate limited")
                tags_to_commits = cached.data
            else:
                logging.info("Returning no data because we are rate limited")
        except GitHubError as e:
            logging.error(
                "Error talking to GitHub while getting tags for project %s: %s",
                project,
                e,
                exc_info=True,
            )

        return tags_to_commits


make_collector = partial(load_and_log, GitHubReleaseCollector)

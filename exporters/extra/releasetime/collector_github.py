"""
EXPERIMENTAL. Reports github releases as "deployments", using the tag's SHA as the image_sha.
"""
from __future__ import annotations

import logging
import urllib.parse
from datetime import datetime
from functools import partial
from typing import Any, Iterable, NamedTuple, Optional, cast

from attrs import field, frozen
from prometheus_client.core import GaugeMetricFamily
from requests import Session

from pelorus import AbstractPelorusExporter
from pelorus.certificates import set_up_requests_certs
from pelorus.config import REDACT, env_vars, load_and_log, log
from pelorus.config.converters import comma_or_whitespace_separated
from pelorus.utils import TokenAuth, join_url_path_components
from provider_common.github import GitHubError, paginate_github, parse_datetime


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

        url = urllib.parse.urlsplit(var)
        parts = url.path.split("/")

        if len(parts) != 2:
            raise ValueError(
                f"Each project needs to be in `organization/repo[?args]` format. {var} is invalid."
            )

        org, repo = parts

        query_params = urllib.parse.parse_qs(url.query)

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


@frozen
class GitHubReleaseCollector(AbstractPelorusExporter):
    # TODO: regex to determine which releases are "prod"?

    projects: set[ProjectSpec] = field(converter=ProjectSpec.all_from_env_var)
    host: str = field(default="api.github.com", metadata=env_vars("GIT_API"))
    token: Optional[str] = field(default=None, metadata=log(REDACT), repr=False)

    _session: Session = field(factory=Session, init=False)

    def __attrs_post_init__(self):
        if not self.projects:
            raise ValueError("No projects specified for GitHub deploytime collector")

        self._session.verify = set_up_requests_certs()

        if self.token:
            self._session.auth = TokenAuth(self.token)

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

    def _get_releases_for_project(self, project: ProjectSpec) -> Iterable[Release]:
        """
        Get all releases for a project.

        If a release is missing necessary data, it won't be yielded, but will be logged.

        Will stop yielding if there is a GitHubError for any of the reasons outlined in paginate_github.
        """

        try:
            first_url = f"https://{self.host}/" + join_url_path_components(
                "repos", project.organization, project.repo, "releases"
            )
            for release in paginate_github(self._session, first_url):
                release = cast(dict[str, Any], release)
                if release["draft"]:
                    continue
                yield Release.from_json(release)
        except GitHubError as e:
            logging.error(
                "Error while getting GitHub response for project %s: %s",
                project,
                e,
                exc_info=True,
            )

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

        tags_to_commits = {}

        try:
            url = f"https://{self.host}/" + join_url_path_components(
                "repos", project.organization, project.repo, "tags"
            )
            for tag in paginate_github(self._session, url):
                tag_name = tag["name"]

                if tag_name in tags:
                    tags_to_commits[tag_name] = tag["commit"]["sha"]
        except GitHubError as e:
            logging.error(
                "Error talking to GitHub while getting tags for project %s: %s",
                project,
                e,
                exc_info=True,
            )

        return tags_to_commits


make_collector = partial(load_and_log, GitHubReleaseCollector)

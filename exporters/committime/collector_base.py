#!/usr/bin/env python3
#
# Copyright Red Hat
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

from __future__ import annotations

import logging
import re
from abc import abstractmethod
from datetime import datetime
from typing import Any, Iterable, Optional

import attrs
from attrs import define, field, frozen
from openshift.dynamic import DynamicClient
from prometheus_client.core import GaugeMetricFamily

import pelorus
from committime import CommitInfo, CommitMetric, GitRepo
from pelorus.config import env_vars
from pelorus.config.converters import comma_separated, pass_through
from pelorus.deserialization import deserialize, nested, retain_source
from pelorus.utils import Url
from pelorus.utils.openshift_utils import CommonResourceInstance, R

# Custom annotations env for the Build
# Default ones are in the CommitMetric._ANNOTATION_MAPPIG
COMMIT_HASH_ANNOTATION_ENV = "COMMIT_HASH_ANNOTATION"
COMMIT_REPO_URL_ANNOTATION_ENV = "COMMIT_REPO_URL_ANNOTATION"
COMMIT_DATE_ANNOTATION_ENV = "COMMIT_DATE_ANNOTATION"


class UnsupportedGITProvider(Exception):
    """
    Exception raised for unsupported GIT provider
    """

    def __init__(self, message):
        self.message = message
        super().__init__(message)


@define(kw_only=True)
class AbstractCommitCollector(pelorus.AbstractPelorusExporter):
    """
    Base class for a CommitCollector.
    This class should be extended for the system which contains the commit information.
    """

    kube_client: DynamicClient = field()
    namespaces: set[str] = field(factory=set, converter=comma_separated(set))

    hash_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPING["commit_hash"],
        metadata=env_vars(COMMIT_HASH_ANNOTATION_ENV),
    )

    committime_cache: dict[str, Optional[datetime]] = field(factory=dict, init=False)
    "Caches the commit time per commit hash"

    def collect(self):
        commit_metric = GaugeMetricFamily(
            "commit_timestamp",
            "Commit timestamp",
            labels=["namespace", "app", "commit", "image_sha"],
        )

        commit_metrics = self.generate_metrics()

        for my_metric in commit_metrics:
            logging.info(
                "Collected commit_timestamp{ namespace=%s, app=%s, commit=%s, image_sha=%s } %s",
                my_metric.namespace,
                my_metric.name,
                my_metric.commit_hash,
                my_metric.image_hash,
                my_metric.commit_timestamp,
            )
            commit_metric.add_metric(
                [
                    my_metric.namespace,
                    my_metric.name,
                    my_metric.commit_hash,
                    my_metric.image_hash,
                ],
                my_metric.commit_timestamp.timestamp(),
            )
        yield commit_metric

    @abstractmethod
    def generate_metrics(self) -> Iterable[CommitMetric]:
        "Create metrics based on whatever source makes sense for the implementation."
        ...

    def _get_openshift_obj_by_app(self, openshift_objs: list[R]) -> dict[str, list[R]]:
        "Group openshift objects by their app label."
        app_label = self.app_label

        items_by_app: dict[str, list[R]] = {}

        for item in openshift_objs:
            app = item.metadata.labels.get(app_label)
            if not app:
                continue

            app_item_list = items_by_app.setdefault(app, [])
            app_item_list.append(item)

        return items_by_app

    def _get_commit_hash_from_annotations(
        self, annotations: dict[str, str]
    ) -> Optional[str]:
        if commit_hash := annotations.get(self.hash_annotation_name):
            logging.debug(
                "Commit hash provided by annotation '%s': %s",
                self.hash_annotation_name,
                commit_hash,
            )
        return commit_hash


@frozen
class Build(CommonResourceInstance):
    strategy: str = field(metadata=nested("spec.strategy.type"))
    status: str = field(metadata=nested("status.phase"))

    openshift_source: Any = field(metadata=retain_source())

    image_hash: Optional[str] = field(
        default=None, metadata=nested("status.output.to.imageDigest")
    )
    repo_url: Optional[str] = field(
        default=None, metadata=nested("spec.source.git.uri")
    )
    commit_hash: Optional[str] = field(
        default=None, metadata=nested("spec.revision.git.commit")
    )
    config_namespace: Optional[str] = field(
        default=None, metadata=nested("status.config.namespace")
    )
    config_name: Optional[str] = field(
        default=None, metadata=nested("status.config.name")
    )


@define(kw_only=True)
class AbstractGitCommitCollector(AbstractCommitCollector):
    "Base class for a git server based collector."

    username: str = field()
    token: str = field(repr=False)

    git_api: Optional[Url] = field(
        default=None,
        converter=attrs.converters.optional(pass_through(Url, Url.parse)),
    )

    tls_verify: bool = field(default=True)

    repo_url_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPING["repo_url"],
        metadata=env_vars(COMMIT_REPO_URL_ANNOTATION_ENV),
    )

    def __attrs_post_init__(self):
        if not (self.username and self.token):
            logging.warning(
                "No API_USER and no TOKEN given. This is okay for public repositories only."
            )
        elif (self.username and not self.token) or (not self.username and self.token):
            logging.warning(
                "username and token must both be set, or neither should be set. Unsetting both."
            )
            self.username = ""
            self.token = ""

    def _get_watched_namespaces(self) -> set[str]:
        watched_namespaces = self.namespaces
        if not watched_namespaces:
            logging.info("No namespaces specified, watching all namespaces")
            v1_namespaces = self.kube_client.resources.get(
                api_version="v1", kind="Namespace"
            )
            watched_namespaces = {
                namespace.metadata.name for namespace in v1_namespaces.get().items
            }
        logging.info("Watching namespaces: %s" % (watched_namespaces))
        return watched_namespaces

    def generate_metrics(self) -> Iterable[CommitMetric]:
        "Create metrics from all labeled builds."
        # This will loop and look at OCP builds (calls get_git_commit_time)

        watched_namespaces = self._get_watched_namespaces()

        metrics = []
        for namespace in watched_namespaces:
            # Initialized variables
            builds = []
            builds_by_app = {}
            app_label = self.app_label
            logging.debug(
                "Searching for builds with label: %s in namespace: %s"
                % (app_label, namespace)
            )

            v1_builds = self.kube_client.resources.get(
                api_version="build.openshift.io/v1", kind="Build"
            )
            # only use builds that have the app label
            builds = v1_builds.get(namespace=namespace, label_selector=app_label)

            builds = [
                deserialize(
                    build,
                    Build,
                    src_name="OpenShift dynamic Build",
                    target_name="build info",
                )
                for build in builds.items
            ]

            builds_by_app = self._get_openshift_obj_by_app(builds)

            if builds_by_app:
                metrics += self.get_metrics_from_apps(builds_by_app, namespace)

        return metrics

    @abstractmethod
    def get_commit_time(self, commit_input: CommitInfo) -> Optional[datetime]:
        # This will perform the API calls and parse out the necessary fields into metrics
        pass

    def get_metrics_from_apps(self, apps: dict[str, list[Build]], namespace: str):
        """Expects a sorted array of build data sorted by app label"""
        metrics = []
        for app in apps:

            builds = apps[app]
            jenkins_builds = [
                build for build in builds if build.strategy == "JenkinsPipeline"
            ]
            # TODO: do we actually care about the strategy type itself?
            # If the data is present, then who cares? Duck typing, just like python.
            code_builds = [
                build
                for build in builds
                if build.strategy in {"Source", "Binary", "Docker"}
            ]

            # assume for now that there will only be one repo/branch per app
            # For jenkins pipelines, we need to grab the repo data
            # then find associated s2i/docker builds from which to pull commit & image data
            if jenkins_builds:
                repo_url = self.get_repo_from_jenkins(
                    jenkins_builds[0].openshift_source
                )
            else:
                repo_url = None
            logging.debug("Repo URL for app %s is currently %s", app, repo_url)

            for build in code_builds:
                try:
                    metric = self.get_metric_from_build(build, app, namespace, repo_url)
                    if metric:
                        logging.debug("Adding metric for app %s" % app)
                        metrics.append(metric)
                except Exception:
                    logging.error(
                        "Cannot collect metrics from build: %s" % (build.metadata.name)
                    )

        return metrics

    def get_metric_from_build(
        self,
        build: Build,
        app: str,
        namespace: str,
        repo_url: Optional[str],
    ) -> Optional[CommitMetric]:
        try:
            if not self._is_build_ready(namespace, build):
                return None

            if build.image_hash is None:
                logging.warning(
                    "Build %s/%s for app %s is missing an image hash, skipping",
                    namespace,
                    build.metadata.name,
                    app,
                )
                return None

            missing = []

            if not (repo_url := self._get_repo_url(repo_url, build)):
                missing.append("repo URL")

            commit_hash = build.commit_hash or self._get_commit_hash_from_annotations(
                build.metadata.annotations
            )

            if not commit_hash:
                missing.append("commit hash")

            if missing:
                logging.warning(
                    "Missing %s for build %s/%s for app %s",
                    " and ".join(missing),
                    namespace,
                    build.metadata.name,
                    app,
                )
                return None

            assert repo_url and commit_hash

            input_ = CommitInfo(GitRepo.from_url(repo_url), commit_hash)

            timestamp = self._get_commit_timestamp(input_)

            if not timestamp:
                # already logged
                return None

            return CommitMetric(
                app,
                namespace=namespace,
                commit_hash=commit_hash,
                commit_timestamp=timestamp,
                image_hash=build.image_hash,
            )
        except Exception:
            logging.error(
                "Error encountered while getting CommitMetric info.", exc_info=True
            )
            return None

    def _get_repo_url(
        self,
        repo_url: Optional[str],  # TODO: will be removed with jenkins support
        build: Build,
    ) -> Optional[str]:
        # Logic to get repo_url, first conditon wins
        # 1. Gather repo_url from the build from spec.source.git.uri
        # 2. Check if repo_url was passed to the function and use it
        # 3. Get repo_url from annotations
        # 4. Get repo_url from parent BuildConfig

        if build.repo_url:
            logging.debug(
                "Repo URL for build %s provided by 'spec.source.git.uri': %s",
                build.metadata.name,
                build.repo_url,
            )
            return build.repo_url
        elif repo_url:
            return repo_url
        elif annotation := build.metadata.annotations.get(
            self.repo_url_annotation_name
        ):
            logging.debug(
                "Repo URL for build %s provided by '%s': %s",
                build.metadata.name,
                self.repo_url_annotation_name,
                annotation,
            )
            return annotation
        elif repo_url := self._get_repo_from_build_config(build):
            return repo_url
        else:
            return None

    def _is_build_ready(self, namespace: str, build: Build) -> bool:
        """
        Determine if a build is ready to be examined.

        There's a few reasons we would stop early:
          - the build is new/pending/running and doesn't have an image yet.
          - the build failed/error'd/cancelled.
        These are valid conditions and we shouldn't clog the logs warning about it.
        However, if it's new/pending/running and _does_ have an image, we might as well continue.
        """
        if build.status in {"Failed", "Error", "Cancelled"}:
            logging.debug(
                "Build %s/%s had status %s, skipping",
                namespace,
                build.metadata.name,
                build.status,
            )
            return False
        elif build.status in {"New, Pending", "Running"}:
            if build.image_hash is None:
                logging.debug(
                    "Build %s/%s has status %s and doesn't have an image_hash yet, skipping",
                    namespace,
                    build.metadata.name,
                    build.status,
                )
                return False
            else:
                return True
        else:
            return True

    # TODO: datetime
    def _get_commit_timestamp(self, input_: CommitInfo) -> Optional[datetime]:
        """
        Check the cache for the commit_time.
        If absent, call the API implemented by the subclass.
        """
        if timestamp := self.committime_cache.get(input_.commit_hash):
            logging.debug(
                "Returning sha: %s, commit_timestamp: %s, from cache.",
                input_.commit_hash,
                timestamp,
            )
            return timestamp

        logging.debug(
            "sha: %s, commit_timestamp not found in cache, executing API call.",
            input_.commit_hash,
        )
        try:
            timestamp = self.get_commit_time(input_)
            if timestamp is None:
                logging.warning(
                    "Failed to get timestamp for commit %s at %s",
                    input_.commit_hash,
                    input_.repo_url,
                )
            else:
                # Add the timestamp to the cache
                self.committime_cache[input_.commit_hash] = timestamp

            return timestamp
        except UnsupportedGITProvider as ex:
            logging.warning(ex)
            return None

    def get_repo_from_jenkins(self, jenkins_build: Any) -> Optional[str]:
        # First, check for cases where the source url is in pipeline params
        git_repo_regex = re.compile(r"((\w+://)|(.+@))([\w\d\.]+)(:[\d]+){0,1}/*(.*)")
        for env in jenkins_build.spec.strategy.jenkinsPipelineStrategy.env:
            logging.debug("Searching %s=%s for git urls" % (env.name, env.value))
            try:
                result = git_repo_regex.match(env.value)
                if result:
                    logging.debug("Found result %s" % env.name)
                    return env.value
            except TypeError:
                # TODO: this is likely a holdover from either trying to
                # use .value on None, or passing None to match.
                # Should clean this up.
                pass

        try:
            # Then default to the repo listed in '.spec.source.git'
            return jenkins_build.spec.source.git.uri
        except AttributeError:
            logging.debug(
                "JenkinsPipelineStrategy build %s has no git repo configured. Will check for source URLs in params.",
                jenkins_build.metadata.name,
            )
        # If no repo is found, we will return None, which will be handled later on

    def _get_repo_from_build_config(self, build: Build) -> Optional[str]:
        """
        Determines the repository url from the parent BuildConfig that created the Build resource in case
        the BuildConfig has the git uri but the Build does not
        :param build: the Build resource
        :return: repo_url as a str or None if not found
        """
        v1_build_configs = self.kube_client.resources.get(
            api_version="build.openshift.io/v1", kind="BuildConfig"
        )
        build_config = v1_build_configs.get(
            namespace=build.config_namespace, name=build.config_name
        )

        if build_config and (
            git_uri := deserialize(build_config, BuildConfigGitUri).git_uri
        ):
            # TODO: why does this add `.git` ?
            if not git_uri.endswith(".git"):
                git_uri += ".git"

            logging.debug(
                "Repo URL for build %s provided by BuildConfig '%s': %s",
                build.metadata.name,
                self.repo_url_annotation_name,
                git_uri,
            )
            return git_uri

        return None


@attrs.frozen
class BuildConfigGitUri:
    git_uri: Optional[str] = attrs.field(
        default=None, metadata=nested("spec.source.git.uri")
    )

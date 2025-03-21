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
from typing import ClassVar, Iterable, Optional

import attrs
from attrs import define, field
from jsonpath_ng import parse
from openshift.dynamic import DynamicClient
from prometheus_client.core import GaugeMetricFamily

import pelorus
from committime import CommitMetric, commit_metric_from_build
from pelorus.config import env_vars
from pelorus.config.converters import comma_separated, pass_through
from pelorus.utils import Url, get_nested
from provider_common import format_app_name

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

    collector_name: ClassVar[str]

    kube_client: DynamicClient = field()

    username: str = field()
    token: str = field(repr=False)

    namespaces: set[str] = field(factory=set, converter=comma_separated(set))

    prod_label: str = field(default=pelorus.DEFAULT_PROD_LABEL)

    git_api: Optional[Url] = field(
        default=None,
        converter=attrs.converters.optional(pass_through(Url, Url.parse)),
    )

    tls_verify: bool = field(default=True)

    commit_dict: dict[str, Optional[CommitMetric]] = field(factory=dict, init=False)

    # TODO hash_annotation_name and repo_url_annotation_name seem to be
    # unnecessary
    hash_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPIG["commit_hash"],
        metadata=env_vars(COMMIT_HASH_ANNOTATION_ENV),
    )

    repo_url_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPIG["repo_url"],
        metadata=env_vars(COMMIT_REPO_URL_ANNOTATION_ENV),
    )

    def __attrs_post_init__(self):
        self.commit_dict = dict()
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

    def collect(self):
        commit_metric = GaugeMetricFamily(
            "commit_timestamp",
            "Commit timestamp",
            labels=["namespace", "app", "commit", "image_sha", "commit_link"],
        )

        commit_metrics = self.generate_metrics()

        for my_metric in commit_metrics:
            logging.debug(
                "Collected commit_timestamp{ namespace=%s, app=%s, commit=%s, image_sha=%s, commit_link=%s } %s"
                % (
                    my_metric.namespace,
                    my_metric.name,
                    my_metric.commit_hash,
                    my_metric.image_hash,
                    my_metric.commit_link,
                    str(float(my_metric.commit_timestamp)),
                )
            )
            commit_metric.add_metric(
                [
                    my_metric.namespace,
                    format_app_name(my_metric.name),
                    my_metric.commit_hash,
                    my_metric.image_hash,
                    my_metric.commit_link,
                ],
                my_metric.commit_timestamp,
            )
        yield commit_metric

    def _get_watched_namespaces(self) -> set[str]:
        watched_namespaces = self.namespaces
        if not watched_namespaces:
            logging.debug("No namespaces specified, watching all namespaces")
            v1_namespaces = self.kube_client.resources.get(
                api_version="v1", kind="Namespace"
            )
            watched_namespaces = {
                namespace.metadata.name for namespace in v1_namespaces.get().items
            }
        logging.debug("Watching namespaces: %s" % (watched_namespaces))
        return watched_namespaces

    def _get_openshift_obj_by_app(self, openshift_obj: str) -> Optional[dict]:
        app_label = self.app_label

        # use a jsonpath expression to find all values for the app label
        jsonpath_str = "$['items'][*]['metadata']['labels']['" + str(app_label) + "']"

        jsonpath_expr = parse(jsonpath_str)

        found = jsonpath_expr.find(openshift_obj)

        apps = {match.value for match in found}

        if not apps:
            return None

        items_by_app = {}

        for app in apps:
            items_by_app[app] = list(
                filter(
                    lambda b: b.metadata.labels[app_label] == app, openshift_obj.items
                )
            )

        return items_by_app

    def generate_metrics(self) -> Iterable[CommitMetric]:
        """Method called by the collect to create a list of metrics to publish"""
        # This will loop and look at OCP builds (calls get_git_commit_time)

        watched_namespaces = self._get_watched_namespaces()

        # Initialize metrics list
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

            builds_by_app = self._get_openshift_obj_by_app(builds)

            if builds_by_app:
                metrics += self.get_metrics_from_apps(builds_by_app, namespace)

        return metrics

    @abstractmethod
    def get_commit_time(self, metric) -> Optional[CommitMetric]:
        # This will perform the API calls and parse out the necessary fields into metrics
        pass

    def get_metrics_from_apps(self, apps, namespace):
        """Expects a sorted array of build data sorted by app label"""
        metrics = []
        for app in apps:
            builds = apps[app]
            jenkins_builds = list(
                filter(lambda b: b.spec.strategy.type == "JenkinsPipeline", builds)
            )
            code_builds = list(
                filter(
                    lambda b: b.spec.strategy.type in ["Source", "Binary", "Docker"],
                    builds,
                )
            )
            # assume for now that there will only be one repo/branch per app
            # For jenkins pipelines, we need to grab the repo data
            # then find associated s2i/docker builds from which to pull commit & image data
            repo_url = self.get_repo_from_jenkins(jenkins_builds)
            logging.debug("Repo URL for app %s is currently %s" % (app, repo_url))

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

    def get_metric_from_build(self, build, app, namespace, repo_url):
        errors = []
        try:
            metric = commit_metric_from_build(app, build, errors)

            if not self._is_metric_ready(namespace, metric, build):
                return None

            # Populate annotations and labels required by
            # subsequent _set_ functions.
            metric.annotations = vars(build.metadata.annotations)
            metric.labels = vars(build.metadata.labels)

            metric = self._set_repo_url(metric, repo_url, build, errors)

            metric = self._set_commit_hash_from_annotations(metric, errors)

            metric = self._set_commit_timestamp(metric, errors)

            if errors:
                msg = (
                    f"Missing data for CommitTime metric from Build "
                    f"{namespace}/{build.metadata.name} in app {app}: "
                    f"{'.'.join(str(e) for e in errors)}"
                )
                logging.warning(msg)
                return None

            return metric
        except AttributeError as e:
            # TODO: have we removed all the spots where we could get an AttributeError?
            logging.warning(
                "Build %s/%s in app %s is missing required attributes to collect data. Skipping.",
                namespace,
                build.metadata.name,
                app,
            )
            logging.debug(e, exc_info=True)
            return None
        except Exception as e:
            logging.error("Error encountered while getting CommitMetric info:")
            logging.error(e, exc_info=True)
            return None

    def _set_commit_hash_from_annotations(
        self, metric: CommitMetric, errors: list
    ) -> CommitMetric:
        if not metric.commit_hash:
            commit_hash = metric.annotations.get(self.hash_annotation_name)
            if commit_hash:
                metric.commit_hash = commit_hash
                logging.debug(
                    "Commit hash for build %s provided by '%s'",
                    metric.build_name,
                    metric.commit_hash,
                )
            else:
                errors.append("Couldn't get commit hash from annotations")
        return metric

    def _set_repo_url(
        self, metric: CommitMetric, repo_url: str, build, errors: list
    ) -> CommitMetric:
        # Logic to get repo_url, first conditon wins
        # 1. Gather repo_url from the build from spec.source.git.uri
        # 2. Check if repo_url was passed to the function and use it
        # 3. Get repo_url from annotations
        # 4. Get repo_url from parent BuildConfig

        if metric.repo_url:
            logging.debug(
                "Repo URL for build %s provided by '%s': %s",
                metric.build_name,
                CommitMetric._BUILD_MAPPING["repo_url"][0],
                metric.repo_url,
            )
        elif repo_url:
            metric.repo_url = repo_url
        else:
            repo_from_annotation = metric.annotations.get(self.repo_url_annotation_name)
            if repo_from_annotation:
                metric.repo_url = repo_from_annotation
                logging.debug(
                    "Repo URL for build %s provided by '%s'",
                    metric.build_name,
                    metric.repo_url,
                )
            else:
                metric.repo_url = self._get_repo_from_build_config(build)

        if not metric.repo_url:
            errors.append("Couldn't get repo_url")

        return metric

    def _is_metric_ready(self, namespace: str, metric: CommitMetric, build) -> bool:
        """
        Determine if a build is ready to be examined.

        There's a few reasons we would stop early:
          - the build is new/pending/running and doesn't have an image yet.
          - the build failed/error'd/cancelled.
        These are valid conditions and we shouldn't clog the logs warning about it.
        However, if it's new/pending/running and _does_ have an image, we might as well continue.
        """
        build_status = get_nested(build, "status.phase", default=None)
        if build_status in {"Failed", "Error", "Cancelled"}:
            logging.debug(
                "Build %s/%s had status %s, skipping",
                namespace,
                build.metadata.name,
                build_status,
            )
            return False
        elif build_status in {"New, Pending", "Running"}:
            if metric.image_hash is None:
                logging.debug(
                    "Build %s/%s has status %s and doesn't have an image_hash yet, skipping",
                    namespace,
                    build.metadata.name,
                    build_status,
                )
                return False
            else:
                return True
        else:
            return True

    # TODO: be specific about the API modifying in place or returning a new metric.
    # Right now, it appears to do both.
    def _set_commit_timestamp(
        self, metric: CommitMetric, errors: list
    ) -> Optional[CommitMetric]:
        """
        Check the cache for the commit_time.
        If absent, call the API implemented by the subclass.
        """
        if metric.commit_hash and metric.commit_hash not in self.commit_dict:
            logging.debug(
                "sha: %s, commit_timestamp not found in cache, executing API call.",
                metric.commit_hash,
            )
            try:
                metric = self.get_commit_time(metric)
                logging.debug(f"Metric returned from git provider: {metric}")
            except UnsupportedGITProvider as ex:
                errors.append(ex.message)
                return None
            # If commit time is None, then we could not get the value from the API
            if metric.commit_time is None:
                errors.append("Couldn't get commit time")
            else:
                # Add the timestamp to the cache
                self.commit_dict[metric.commit_hash] = metric
        elif metric.commit_hash:
            metric = self.commit_dict[metric.commit_hash]
            logging.debug(f"Returning metric from cache {metric}")

        return metric

    def get_repo_from_jenkins(self, jenkins_builds):
        if jenkins_builds:
            # First, check for cases where the source url is in pipeline params
            git_repo_regex = re.compile(
                r"((\w+://)|(.+@))([\w\d\.]+)(:[\d]+){0,1}/*(.*)"
            )
            for env in jenkins_builds[0].spec.strategy.jenkinsPipelineStrategy.env:
                logging.debug("Searching %s=%s for git urls" % (env.name, env.value))
                try:
                    result = git_repo_regex.match(env.value)
                except TypeError:
                    result = None
                if result:
                    logging.debug("Found result %s" % env.name)
                    return env.value

            try:
                # Then default to the repo listed in '.spec.source.git'
                return jenkins_builds[0].spec.source.git.uri
            except AttributeError:
                logging.debug(
                    "JenkinsPipelineStrategy build %s has no git repo configured. "
                    % jenkins_builds[0].metadata.name
                    + "Will check for source URLs in params."
                )
        # If no repo is found, we will return None, which will be handled later on

    def _get_repo_from_build_config(self, build):
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
            namespace=build.status.config.namespace, name=build.status.config.name
        )
        if build_config:
            if build_config.spec.source.git:
                git_uri = str(build_config.spec.source.git.uri)
                if git_uri.endswith(".git"):
                    return git_uri
                else:
                    return git_uri + ".git"

        return None

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
import threading
import time
from abc import abstractmethod
from collections import OrderedDict
from typing import Iterable, Optional

import attrs
from attrs import define, field
from kubernetes.dynamic import DynamicClient
from prometheus_client import Counter, Gauge
from prometheus_client.core import GaugeMetricFamily

import pelorus
from committime import CommitMetric, commit_metric_from_build
from pelorus.config import env_vars
from pelorus.config.converters import comma_separated, pass_through
from pelorus.config.log import REDACT, log
from pelorus.utils import Url, get_nested
from provider_common import format_app_name

# Custom annotations env for the Build
# Default ones are in the CommitMetric._ANNOTATION_MAPPING
COMMIT_HASH_ANNOTATION_ENV = "COMMIT_HASH_ANNOTATION"
COMMIT_REPO_URL_ANNOTATION_ENV = "COMMIT_REPO_URL_ANNOTATION"
COMMIT_DATE_ANNOTATION_ENV = "COMMIT_DATE_ANNOTATION"

# Pre-compiled regex for matching git repo URLs in Jenkins pipeline env vars
_GIT_REPO_RE = re.compile(r"((\w+://)|(.+@))([\w\d\.]+)(:[\d]+)?/*(.*)")
# Regex to strip embedded credentials from URLs before logging
_URL_USERINFO_RE = re.compile(r"(https?://)([^@]+)@")
# Pre-compiled regex for validating app_label values
_VALID_APP_LABEL_RE = re.compile(r"^[A-Za-z0-9_./-]+$")

_collection_duration = Gauge(
    "pelorus_committime_collection_duration_seconds",
    "Duration of the last committime metric collection in seconds",
)
_collection_errors = Counter(
    "pelorus_committime_collection_errors_total",
    "Total number of committime metric collection errors",
)
_build_failures = Counter(
    "pelorus_committime_build_failures_total",
    "Total number of individual build metric collection failures",
)
_last_collection_count = Gauge(
    "pelorus_committime_last_collection_count",
    "Number of metrics returned by the last committime collection",
)


class UnsupportedGITProvider(Exception):
    pass


_KNOWN_GIT_PROVIDERS = frozenset({"github", "gitlab", "gitea", "bitbucket", "azure"})


def _sanitize_url(url: str) -> str:
    """Strip embedded credentials (user:pass@) from a URL for safe logging."""
    if not url:
        return url
    return _URL_USERINFO_RE.sub(r"\1", url)


def check_provider_support(server_string: str, provider_name: str) -> None:
    """Raise UnsupportedGITProvider if server_string contains a known provider other than provider_name."""
    for other in _KNOWN_GIT_PROVIDERS - {provider_name}:
        if other in server_string:
            raise UnsupportedGITProvider(
                f"Skipping non {provider_name} server, found {server_string}"
            )


@define(kw_only=True)
class AbstractCommitCollector(pelorus.AbstractPelorusExporter):
    """Base class for commit time collectors that fetch timestamps from different git providers."""

    kube_client: DynamicClient = field()

    username: str = field()
    token: str = field(repr=False, metadata=log(REDACT))

    namespaces: set[str] = field(factory=set, converter=comma_separated(set))

    prod_label: str = field(default=pelorus.DEFAULT_PROD_LABEL)

    git_api: Optional[Url] = field(
        default=None,
        converter=attrs.converters.optional(pass_through(Url, Url.parse)),
    )

    tls_verify: bool = field(default=True)

    commit_dict: OrderedDict[str, tuple[Optional[str], Optional[float], Optional[str]]] = field(factory=OrderedDict, init=False)
    _build_config_cache: OrderedDict[tuple[str, str], Optional[str]] = field(factory=OrderedDict, init=False)
    _cache_lock: threading.Lock = field(factory=threading.Lock, init=False)

    _COMMIT_CACHE_MAX = 10_000
    _BUILD_CONFIG_CACHE_MAX = 1_000

    hash_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPING["commit_hash"],
        metadata=env_vars(COMMIT_HASH_ANNOTATION_ENV),
    )

    repo_url_annotation_name: str = field(
        default=CommitMetric._ANNOTATION_MAPPING["repo_url"],
        metadata=env_vars(COMMIT_REPO_URL_ANNOTATION_ENV),
    )

    _COMMIT_METRIC_NAME = "commit_timestamp"
    _COMMIT_METRIC_HELP = "Commit timestamp"
    _COMMIT_METRIC_LABELS = ["namespace", "app", "commit", "image_sha", "commit_link"]

    def __attrs_post_init__(self):
        if not _VALID_APP_LABEL_RE.match(str(self.app_label)):
            raise ValueError(f"Invalid app_label: {self.app_label!r}")
        if bool(self.username) != bool(self.token):
            logging.warning(
                "username and token must both be set, or neither should be set. Unsetting both."
            )
            self.username = ""
            self.token = ""
        elif not self.username and not self.token:
            logging.warning(
                "No API_USER and no TOKEN given. This is okay for public repositories only."
            )

    def _new_commit_metric(self):
        return GaugeMetricFamily(
            self._COMMIT_METRIC_NAME,
            self._COMMIT_METRIC_HELP,
            labels=self._COMMIT_METRIC_LABELS,
        )

    def describe(self) -> list[GaugeMetricFamily]:
        return [self._new_commit_metric()]

    def collect(self) -> Iterable[GaugeMetricFamily]:
        logging.debug("collect: start")
        start = time.monotonic()
        collected_count = 0
        try:
            commit_metric = self._new_commit_metric()

            commit_metrics = self.generate_metrics()

            for my_metric in commit_metrics:
                if my_metric.commit_timestamp is None:
                    logging.warning(
                        "Skipping metric with no commit_timestamp: app=%s, commit=%s",
                        my_metric.name, my_metric.commit_hash,
                    )
                    continue
                logging.debug(
                    "Collected commit_timestamp{ namespace=%s, app=%s, commit=%s, image_sha=%s, commit_link=%s } %s",
                    my_metric.namespace,
                    my_metric.name,
                    my_metric.commit_hash,
                    my_metric.image_hash,
                    my_metric.commit_link,
                    my_metric.commit_timestamp,
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
                collected_count += 1
            yield commit_metric
        except Exception:
            _collection_errors.inc()
            logging.error("Commit time metric collection failed", exc_info=True)
            yield self._new_commit_metric()
        finally:
            duration = time.monotonic() - start
            _collection_duration.set(duration)
            _last_collection_count.set(collected_count)
            logging.info("collect: %d metrics in %.2fs", collected_count, duration)

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
        logging.debug("Watching namespaces: %s", watched_namespaces)
        return watched_namespaces

    def _get_openshift_obj_by_app(self, openshift_obj) -> dict[str, list]:
        app_label = self.app_label

        items = getattr(openshift_obj, "items", None)
        if not items:
            return {}

        items_by_app: dict[str, list] = {}

        for item in items:
            app_name = item.metadata.labels.get(app_label)
            if app_name:
                items_by_app.setdefault(app_name, []).append(item)

        return items_by_app

    def generate_metrics(self) -> Iterable[CommitMetric]:
        """Generate metrics from builds across watched namespaces."""

        watched_namespaces = self._get_watched_namespaces()

        app_label = self.app_label
        v1_builds = self.kube_client.resources.get(
            api_version="build.openshift.io/v1", kind="Build"
        )
        for namespace in watched_namespaces:
            logging.debug(
                "Searching for builds with label: %s in namespace: %s",
                app_label, namespace,
            )

            builds = v1_builds.get(namespace=namespace, label_selector=app_label)

            builds_by_app = self._get_openshift_obj_by_app(builds)

            if builds_by_app:
                yield from self.get_metrics_from_apps(builds_by_app, namespace)

    @abstractmethod
    def get_commit_time(self, metric) -> Optional[CommitMetric]:
        """Get commit timestamp from the git provider API for the given metric."""

    def get_metrics_from_apps(self, apps, namespace):
        """Expects a dict of builds grouped by app label."""
        failed_builds = 0
        total_builds = 0
        for app, builds in apps.items():
            jenkins_builds = []
            code_builds = []
            for b in builds:
                try:
                    strategy_type = b.spec.strategy.type
                except (AttributeError, TypeError):
                    _build_failures.inc()
                    logging.warning(
                        "Build %s/%s has no strategy type, skipping",
                        namespace, getattr(getattr(b, "metadata", None), "name", "?"),
                    )
                    continue
                if strategy_type == "JenkinsPipeline":
                    jenkins_builds.append(b)
                elif strategy_type in ("Source", "Binary", "Docker"):
                    code_builds.append(b)
            # For Jenkins pipelines, grab repo data then find associated
            # Source/Binary/Docker builds from which to pull commit & image data
            repo_url = self.get_repo_from_jenkins(jenkins_builds)
            logging.debug("Repo URL for app %s is currently %s", app, _sanitize_url(repo_url) if repo_url else repo_url)

            for build in code_builds:
                total_builds += 1
                try:
                    metric = self.get_metric_from_build(build, app, namespace, repo_url)
                    if metric:
                        logging.debug("Adding metric for app %s", app)
                        yield metric
                except Exception:
                    failed_builds += 1
                    _build_failures.inc()
                    logging.error(
                        "Cannot collect metrics from build: %s",
                        build.metadata.name,
                        exc_info=True,
                    )

        if failed_builds:
            logging.warning(
                "Failed to collect metrics from %d/%d builds in namespace %s",
                failed_builds, total_builds, namespace,
            )

    def get_metric_from_build(self, build, app, namespace, repo_url):
        errors = []
        try:
            metric = commit_metric_from_build(app, build, errors)

            if not self._is_metric_ready(namespace, metric, build):
                return None

            # Populate annotations and labels required by
            # subsequent _set_ functions.
            metric.annotations = vars(build.metadata.annotations) if build.metadata.annotations else {}
            metric.labels = vars(build.metadata.labels) if build.metadata.labels else {}

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
            _build_failures.inc()
            logging.warning(
                "Build %s/%s in app %s is missing required attributes to collect data. Skipping.",
                namespace,
                build.metadata.name,
                app,
            )
            logging.debug("Missing attributes: %s", e, exc_info=True)
            return None
        except Exception:
            _build_failures.inc()
            logging.error(
                "Error getting CommitMetric for build %s/%s in app %s",
                namespace, build.metadata.name, app, exc_info=True,
            )
            return None

    def _set_commit_hash_from_annotations(
        self, metric: CommitMetric, errors: list
    ) -> CommitMetric:
        if not metric.commit_hash:
            commit_hash = metric.annotations.get(self.hash_annotation_name)
            if commit_hash:
                metric.commit_hash = commit_hash
                logging.debug(
                    "Commit hash for build %s found in annotation '%s'",
                    metric.build_name,
                    self.hash_annotation_name,
                )
            else:
                errors.append("Couldn't get commit hash from annotations")
        return metric

    def _set_repo_url(
        self, metric: CommitMetric, repo_url: str, build, errors: list
    ) -> CommitMetric:
        # Logic to get repo_url, first condition wins
        # 1. Gather repo_url from the build from spec.source.git.uri
        # 2. Check if repo_url was passed to the function and use it
        # 3. Get repo_url from annotations
        # 4. Get repo_url from parent BuildConfig

        if metric.repo_url:
            logging.debug(
                "Repo URL for build %s provided by '%s': %s",
                metric.build_name,
                CommitMetric._BUILD_MAPPING["repo_url"][0],
                _sanitize_url(metric.repo_url),
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
                    _sanitize_url(metric.repo_url),
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
        if build_status in {"New", "Pending", "Running"} and metric.image_hash is None:
            logging.debug(
                "Build %s/%s has status %s and doesn't have an image_hash yet, skipping",
                namespace,
                build.metadata.name,
                build_status,
            )
            return False
        return True

    def _set_commit_timestamp(
        self, metric: CommitMetric, errors: list
    ) -> Optional[CommitMetric]:
        """
        Check the cache for the commit_time.
        If absent, call the API implemented by the subclass.
        """
        with self._cache_lock:
            if metric.commit_hash and metric.commit_hash in self.commit_dict:
                commit_time, commit_timestamp, commit_link = self.commit_dict[metric.commit_hash]
                # Move to end for LRU eviction
                self.commit_dict.move_to_end(metric.commit_hash)
                metric.commit_time = commit_time
                metric.commit_timestamp = commit_timestamp
                metric.commit_link = commit_link
                logging.debug("Returning metric from cache for hash %s", metric.commit_hash)
                return metric
            needs_fetch = bool(metric.commit_hash)

        if not needs_fetch:
            return metric

        logging.debug(
            "sha: %s, commit_timestamp not found in cache, executing API call.",
            metric.commit_hash,
        )
        try:
            metric = self.get_commit_time(metric)
            logging.debug("Metric returned from git provider: %s", metric)
        except UnsupportedGITProvider as ex:
            errors.append(str(ex))
            return None
        if metric is None:
            errors.append("get_commit_time returned None")
            return None
        if metric.commit_time is None:
            errors.append("Couldn't get commit time")
        else:
            with self._cache_lock:
                if len(self.commit_dict) >= self._COMMIT_CACHE_MAX:
                    self.commit_dict.popitem(last=False)
                self.commit_dict[metric.commit_hash] = (metric.commit_time, metric.commit_timestamp, metric.commit_link)

        return metric

    def get_repo_from_jenkins(self, jenkins_builds):
        if jenkins_builds:
            # First, check for cases where the source url is in pipeline params
            for env in jenkins_builds[0].spec.strategy.jenkinsPipelineStrategy.env or []:
                logging.debug("Searching env var %s for git urls", env.name)
                try:
                    result = _GIT_REPO_RE.match(env.value)
                except TypeError:
                    result = None
                if result:
                    logging.debug("Found result %s", env.name)
                    return env.value

            try:
                # Then default to the repo listed in '.spec.source.git'
                return jenkins_builds[0].spec.source.git.uri
            except AttributeError:
                logging.debug(
                    "JenkinsPipelineStrategy build %s has no git repo configured. "
                    "Will check for source URLs in params.",
                    jenkins_builds[0].metadata.name,
                )
        # If no repo is found, we will return None, which will be handled later on

    def _get_repo_from_build_config(self, build):
        """Get repo URL from the parent BuildConfig when the Build itself lacks a git URI."""
        bc_ns = build.status.config.namespace
        bc_name = build.status.config.name
        cache_key = (bc_ns, bc_name)

        with self._cache_lock:
            if cache_key in self._build_config_cache:
                self._build_config_cache.move_to_end(cache_key)
                return self._build_config_cache[cache_key]

        result = None
        v1_build_configs = self.kube_client.resources.get(
            api_version="build.openshift.io/v1", kind="BuildConfig"
        )
        build_config = v1_build_configs.get(namespace=bc_ns, name=bc_name)
        if build_config:
            if build_config.spec.source.git:
                git_uri = str(build_config.spec.source.git.uri)
                if not git_uri.endswith(".git"):
                    git_uri = git_uri + ".git"
                result = git_uri

        with self._cache_lock:
            if len(self._build_config_cache) >= self._BUILD_CONFIG_CACHE_MAX:
                self._build_config_cache.popitem(last=False)
            self._build_config_cache[cache_key] = result
        return result

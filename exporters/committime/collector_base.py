from __future__ import annotations

import json
import logging
import re
from abc import abstractmethod
from collections.abc import Mapping
from typing import Any, Iterable, Optional, Tuple

import openshift.dynamic
import openshift.dynamic.exceptions
from committime import CommitMetric
from jsonpath_ng import parse
from prometheus_client.core import GaugeMetricFamily

import pelorus
from pelorus.utils import TypedString, get_nested, name_value_attrs_to_dict


class AbstractCommitCollector(pelorus.AbstractPelorusExporter):
    """
    Base class for a CommitCollector.
    This class should be extended for the system which contains the commit information.
    """

    _kube_client: openshift.dynamic.DynamicClient
    _git_uri_annotation: str
    _commit_dict: dict[str, float]
    """The name of the annotation to check if no repo_url comes from jenkins and
    the build spec doesn't have git information.
    """

    def __init__(
        self,
        kube_client,
        username,
        token,
        namespaces,
        apps,
        collector_name,
        timedate_format,
        git_api=None,
        tls_verify=None,
        git_uri_annotation: str = "gitUri",
    ):
        """Constructor"""
        self._kube_client = kube_client
        self._username = username
        self._token = token
        self._namespaces = namespaces
        self._apps = apps
        self._git_api = git_api
        self._tls_verify = tls_verify
        self._commit_dict = {}
        self._timedate_format = timedate_format
        self._collector_name = collector_name
        self._git_uri_annotation = git_uri_annotation
        logging.info("=====Using %s Collector=====" % (self._collector_name))

    def collect(self):
        commit_metric = GaugeMetricFamily(
            "commit_timestamp",
            "Commit timestamp",
            labels=["namespace", "app", "commit", "image_sha"],
        )
        commit_metrics = self.generate_metrics()
        for my_metric in commit_metrics:
            logging.info(
                "Collected commit_timestamp{ namespace=%s, app=%s, commit=%s, image_sha=%s } %s"
                % (
                    my_metric.namespace,
                    my_metric.name,
                    my_metric.commit_hash,
                    my_metric.image_hash,
                    str(float(my_metric.commit_timestamp)),  # type: ignore
                )
            )
            commit_metric.add_metric(
                [
                    my_metric.namespace,
                    my_metric.name,
                    my_metric.commit_hash,
                    my_metric.image_hash,
                ],
                my_metric.commit_timestamp,
            )
            yield commit_metric

    def generate_metrics(self) -> Iterable[CommitMetric]:
        """Method called by the collect to create a list of metrics to publish"""
        # This will loop and look at OCP builds (calls get_git_commit_time)
        if not self._namespaces:
            logging.info("No namespaces specified, watching all namespaces")
            v1_namespaces = self._kube_client.resources.get(
                api_version="v1", kind="Namespace"
            )
            self._namespaces = [
                namespace.metadata.name for namespace in v1_namespaces.get().items
            ]
        else:
            logging.info("Watching namespaces: %s" % (self._namespaces))

        # Initialize metrics list
        metrics = []
        for namespace in self._namespaces:
            app_label_key = pelorus.get_app_label()
            logging.debug(
                "Searching for builds with label: %s in namespace: %s"
                % (app_label_key, namespace)
            )
            # This get all Builds in our cluster
            v1_builds = self._kube_client.resources.get(
                api_version="build.openshift.io/v1", kind="Build"
            )
            # only use builds that have an app label
            builds = v1_builds.get(namespace=namespace, label_selector=app_label_key)

            try:
                v1_tekton = self._kube_client.resources.get(
                    api_version="tekton.dev/v1beta1", kind="PipelineRun"
                )
                # only use PipelineRun that have an app label
                pipeline_runs = v1_tekton.get(
                    namespace=namespace, label_selector=app_label_key
                )
            except openshift.dynamic.exceptions.ResourceNotFoundError:
                pipeline_runs = pelorus.NoOpResourceInstance()

            # use a jsonpath expression to find all possible values for the app label
            jsonpath_str = f"$['items'][*]['metadata']['labels']['{app_label_key}']"
            jsonpath_expr = parse(jsonpath_str)

            apps: set[str] = {match.value for match in jsonpath_expr.find(builds)}
            pipeline_run_app_labels: set[str] = {
                match.value for match in jsonpath_expr.find(pipeline_runs)
            }

            builds_by_app: dict[str, list] = {
                app: [
                    build
                    for build in builds.items
                    if build.metadata.labels[app_label_key] == app
                ]
                for app in apps
            }

            metrics += self._get_metrics_from_apps(builds_by_app, namespace)

            runs_by_app: dict[AppLabelValue, list] = {
                AppLabelValue(app_label_value): [
                    run
                    for run in pipeline_runs.items
                    if run.metadata.labels[app_label_key] == app_label_value
                ]
                for app_label_value in pipeline_run_app_labels
            }

            try:
                metrics += self.get_metrics_from_pipelineruns(runs_by_app)
            except Exception as e:
                logging.error(f"Error while getting metrics from Tekton: {e}")

        return metrics

    @abstractmethod
    def get_commit_time(self, metric: CommitMetric) -> CommitMetric:
        # This will perform the API calls and parse out the necessary fields into metrics
        pass

    def _get_metrics_from_apps(
        self, apps: Mapping[str, list], namespace: str
    ) -> list[CommitMetric]:
        """
        Given a mapping of "app" (identified by the app.kubernetes.io/name label by default)
        to a list of openshift builds, obtain commit information from jenkins and/or
        the git forge targed by the subclass of AbstractCommitCollector.
        """
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

                    if not metric:
                        continue

                    logging.debug("Adding metric for app %s" % app)
                    metrics.append(metric)
                except Exception:
                    logging.error(
                        "Cannot collect metrics from build: %s" % (build.metadata.name)
                    )
        return metrics

    def get_metric_from_build(
        self, build, app: str, namespace: str, repo_url: Optional[str]
    ) -> Optional[CommitMetric]:
        """
        Extract repo url information from a Source, Binary, or Docker build.

        Will obtain it from the spec.source.git.uri if present,
        otherwise look for the information in an annotation,
        and then fall back to looking for it in the buildconfig.
        """
        try:
            metric = CommitMetric(app)

            metadata = build.metadata
            labels = metadata.labels
            spec = build.spec

            if not repo_url:
                if spec.source.git:
                    repo_url = spec.source.git.uri
                elif repo_url := get_nested(
                    metadata, ["annotations", self._git_uri_annotation], default=None
                ):
                    pass
                else:
                    repo_url = self._get_repo_from_build_config(build)

            metric.repo_url = repo_url

            if spec.revision:
                commit_sha = spec.revision.git.commit
            else:
                # TODO: check for existence, allow user customization? Annotation instead?
                commit_sha = labels.peloruscommitsha

            metric.build_name = metadata.name
            metric.build_config_name = labels.buildconfig
            metric.namespace = metadata.namespace
            # TODO: replace this with something like labels.__dict__,
            # because at that level an openshift.dynamic.ResourceField's
            # dict should just be dict[str, str].
            # But this requires testing.
            metric.labels = json.loads(str(labels).replace("'", '"'))

            metric.commit_hash = commit_sha
            metric.image_hash = build.status.output.to.imageDigest
            # Check the cache for the commit_time, if not call the API
            metric_ts = self._commit_dict.get(commit_sha)
            if metric_ts is None:
                logging.debug(
                    "sha: %s, commit_timestamp not found in cache, executing API call."
                    % (commit_sha)
                )
                metric = self.get_commit_time(metric)
                # If commit time is None, then we could not get the value from the API
                if metric.commit_time is None:
                    return None
                # Add the timestamp to the cache
                self._commit_dict[metric.commit_hash] = metric.commit_timestamp  # type: ignore
            else:
                # NOTE: only commit_timestamp is updated because that's
                # all the metric needs for prometheus.
                # If this is changed later to do further work with the metric,
                # Be sure to account for this.
                metric.commit_timestamp = self._commit_dict[commit_sha]
                logging.debug(
                    "Returning sha: %s, commit_timestamp: %s, from cache."
                    % (commit_sha, metric.commit_timestamp)
                )

            return metric

        except Exception as e:
            logging.warning(
                "Build %s/%s in app %s is missing required attributes to collect data. Skipping."
                % (namespace, build.metadata.name, app)
            )
            logging.debug(e, exc_info=True)
            return None

    def get_repo_from_jenkins(self, jenkins_builds) -> Optional[str]:

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

    def get_metrics_from_pipelineruns(
        self, pipeline_runs_by_app: Mapping[AppLabelValue, list]
    ) -> list[CommitMetric]:
        """
        Given a mapping from app name to a list of pipeline runs for that app,
        generate metrics for those commits.

        This finds the repo_url and commit_sha by looking through relevant taskruns,
        and looks up time information from the git forge targeted by the subclass
        of AbstractCommitCollector.
        """
        metrics = []
        for app_name, pipeline_run in (
            (app_name, pipeline_run)
            for app_name, pipeline_runs in pipeline_runs_by_app.items()
            for pipeline_run in pipeline_runs
        ):
            try:
                if not _check_pipeline_run_for_success(pipeline_run):
                    logging.debug(
                        f"PipelineRun {pipeline_run.metadata.name} was unsuccessful, skipping"
                    )
                    continue

                metric = CommitMetric(app_name.data)

                # TODO: gracefully degrade
                if (url_and_sha := self._get_url_and_sha(pipeline_run)) is not None:
                    repo_url, commit_sha = url_and_sha
                else:
                    repo_url, commit_sha = None, None

                metric.image_hash = _find_first_image_digest_value(pipeline_run)
                metric.repo_url = repo_url
                metric.commit_hash = commit_sha
                metric.build_name = pipeline_run.metadata.name
                metric.build_config_name = pipeline_run.metadata.labels[
                    "tekton.dev/pipeline"
                ]
                metric.namespace = pipeline_run.metadata.namespace
                labels = pipeline_run.metadata.labels
                # TODO: replace this with something like labels.__dict__,
                # because at that level an openshift.dynamic.ResourceField's
                # dict should just be dict[str, str].
                # But this requires testing.
                metric.labels = json.loads(str(labels).replace("'", '"'))

                # Check the cache for the commit_time, if not call the API
                if commit_sha not in self._commit_dict:
                    logging.debug(
                        "sha: %s, commit_timestamp not found in cache, executing API call."
                        % (commit_sha)
                    )
                    metric = self.get_commit_time(metric)
                    # If commit time is None, then we could not get the value from the API
                    if metric.commit_time is None:
                        continue
                    # Add the timestamp to the cache
                    self._commit_dict[metric.commit_hash] = metric.commit_timestamp  # type: ignore
                else:
                    metric.commit_timestamp = self._commit_dict[commit_sha]  # type: ignore
                    logging.debug(
                        "Returning sha: %s, commit_timestamp: %s, from cache."
                        % (commit_sha, metric.commit_timestamp)
                    )

                if metric:
                    logging.debug("Adding metric for pipeline %s" % app_name)
                    metrics.append(metric)

            except Exception as e:
                logging.error(
                    "Cannot collect metrics from run: %s" % (pipeline_run.metadata.name)
                )
                logging.error(e)

        return metrics

    def _get_repo_from_build_config(self, build):
        """
        Determines the repository url from the parent BuildConfig that created the Build resource in case
        the BuildConfig has the git uri but the Build does not
        :param build: the Build resource
        :return: repo_url as a str or None if not found
        """
        v1_build_configs = self._kube_client.resources.get(
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

    def _find_git_clone_task_name(
        self, pipeline_name: PipelineName, namespace: str
    ) -> Optional[str]:
        """
        Get the Pipeline associated with a given PipelineRun,
        and find the task name for the git-clone ClusterTask, if one exists.
        Used to find the TaskRun that did the git checkout.
        """
        pipeline_resource = self._kube_client.resources.get(
            api_version="tekton.dev/v1beta1", kind="Pipeline"
        )

        pipeline = pipeline_resource.get(namespace=namespace, name=pipeline_name)

        for task in pipeline.spec.tasks:
            if (
                (task_ref := task.taskRef)
                and task_ref.name == "git-clone"
                and task_ref.kind == "ClusterTask"
            ):
                return task.name

    def _get_url_and_sha(self, pipeline_run) -> Optional[Tuple[str, str]]:
        """
        Get the URL and commit SHA from the git-clone task in this PipelineRun.
        """
        namespace = pipeline_run.metadata.namespace
        pipeline_name = PipelineName(pipeline_run.spec.pipelineRef.name)
        git_clone_task_name = self._find_git_clone_task_name(pipeline_name, namespace)
        if git_clone_task_name is None:
            return None

        git_clone_task_run = _find_task_run_by_task_name(
            pipeline_run, git_clone_task_name
        )
        if git_clone_task_run is None:
            return None

        clone_task_results = name_value_attrs_to_dict(
            git_clone_task_run.status.taskResults
        )
        return (clone_task_results["url"], clone_task_results["commit"])


def _find_task_run_by_task_name(pipeline_run, task_name: str) -> Optional[Any]:
    """
    Find the TaskRun reference with the specified `pipelineTaskName` within the PipelineRun.
    """
    task_runs = pipeline_run.status.taskRuns
    if not task_runs:
        return None
    for task_run in task_runs.values():
        if task_run.pipelineTaskName == task_name:
            return task_run


def _find_first_image_digest_value(pipeline_run) -> Optional[str]:
    """
    Find the first `IMAGE_DIGEST` value within any `taskResult` from the TaskRuns in this PipelineRun.
    """
    for task_run in pipeline_run.status.taskRuns.values():
        for item in task_run.status.taskResults:
            if item.name == "IMAGE_DIGEST":
                return item.value


def _check_pipeline_run_for_success(pipeline_run) -> bool:
    """
    Was the given pipelinerun successful?
    """
    # Unsure if this is correct, but I have to see a status field that had more than one condition.
    # Unfortunately, PipelineRun isn't documented in their API spec.
    condition = get_nested(pipeline_run, ["status", "conditions", 0], name="conditions")
    # See https://tekton.dev/docs/pipelines/pipelineruns/#monitoring-execution-status
    # for the logic behind determining failure / success.
    # Since we just care about any type of success, we just check the status field.
    return condition.status == "True"


class PipelineName(TypedString):
    pass


class AppLabelValue(TypedString):
    pass

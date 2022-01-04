from __future__ import annotations

import json
import logging
import re
from abc import abstractmethod
from typing import Iterable

from committime import CommitMetric
from jsonpath_ng import parse
from prometheus_client.core import GaugeMetricFamily

import pelorus


class AbstractCommitCollector(pelorus.AbstractPelorusExporter):
    """
    Base class for a CommitCollector.
    This class should be extended for the system which contains the commit information.
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
                    str(float(my_metric.commit_timestamp)),
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
            # Initialized variables
            builds = []
            pipeline_runs = []
            apps = []
            pipelines = []
            builds_by_app = {}
            runs_by_app = {}
            app_label = pelorus.get_app_label()
            logging.debug(
                "Searching for builds with label: %s in namespace: %s"
                % (app_label, namespace)
            )
            # This get all Builds in our cluster
            v1_builds = self._kube_client.resources.get(
                api_version="build.openshift.io/v1", kind="Build"
            )
            v1_tekton = self._kube_client.resources.get(
                api_version="tekton.dev/v1beta1", kind="PipelineRun"
            )
            # only use builds that have the app label
            builds = v1_builds.get(namespace=namespace, label_selector=app_label)
            # only use PipelineRun that have the app label
            pipeline_runs = v1_tekton.get(namespace=namespace, label_selector=app_label)
            # use a jsonpath expression to find all values for the app label
            jsonpath_str = (
                "$['items'][*]['metadata']['labels']['" + str(app_label) + "']"
            )
            jsonpath_expr = parse(jsonpath_str)

            found = jsonpath_expr.find(builds)
            runs_found = jsonpath_expr.find(pipeline_runs)

            apps = [match.value for match in found]
            pipelines = [match.value for match in runs_found]

            if not apps and not pipelines:
                continue
            elif apps:
                # remove duplicates
                apps = list(dict.fromkeys(apps))
                builds_by_app = {}

                for app in apps:
                    builds_by_app[app] = list(
                        filter(lambda b: b.metadata.labels[app_label] == app, builds.items)
                    )
                
                metrics += self.get_metrics_from_apps(builds_by_app, namespace)
            elif pipelines:
                # remove duplicates
                pipelines = list(dict.fromkeys(pipelines))
                runs_by_app = {}

                for pipeline in pipelines:
                    runs_by_app[pipeline] = list(
                        filter(lambda b: b.metadata.labels[app_label] == pipeline, pipeline_runs.items)
                    )
                
                metrics += self.get_metric_from_pipelineruns(runs_by_app, namespace)

        return metrics

    @abstractmethod
    def get_commit_time(self, metric):
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
                except Exception:
                    logging.error(
                        "Cannot collect metrics from build: %s" % (build.metadata.name)
                    )

                if metric:
                    logging.debug("Adding metric for app %s" % app)
                    metrics.append(metric)
        return metrics

    def get_metric_from_build(self, build, app, namespace, repo_url):
        try:

            metric = CommitMetric(app)

            if not repo_url:
                if build.spec.source.git:
                    repo_url = build.spec.source.git.uri
                elif build.metadata.labels.pelorusgithost:
                    git_host = build.metadata.labels.pelorusgithost
                    git_project = build.metadata.labels.pelorusgitproject
                    git_app = build.metadata.labels.pelorusgitapp
                    git_protocol = build.metadata.labels.pelorusgitprotocol
                    repo_url = git_protocol + "://" + git_host + "/" + git_project + "/" + git_app
                else:
                    repo_url = self._get_repo_from_build_config(build)

            metric.repo_url = repo_url
            commit_sha = build.metadata.labels.peloruscommitsha
            metric.build_name = build.metadata.name
            metric.build_config_name = build.metadata.labels.buildconfig
            metric.namespace = build.metadata.namespace
            labels = build.metadata.labels
            metric.labels = json.loads(str(labels).replace("'", '"'))

            metric.commit_hash = commit_sha
            metric.name = app
            #metric.committer = build.spec.revision.git.author.name
            metric.committer = "default"
            metric.image_location = build.status.outputDockerImageReference
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
                self._commit_dict[metric.commit_hash] = metric.commit_timestamp
            else:
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

    def get_metric_from_pipelineruns(self, pipelines, namespace):
        """Expects a sorted array of build data sorted by app label"""
        metrics = []
        for pipeline in pipelines:
            runs = pipelines[pipeline]

            for run in runs:
                repo_url = 'http://default'
                commit_sha = 'default'
                image_hash = 'default'
                image_location = 'http://default'
                try:
                    # metric = self.get_metric_from_build(build, app, namespace, repo_url)
                    metric = CommitMetric(pipeline)
                    # By convention need to get image location from PARAMS
                    params = run.status.pipelineSpec.params
                    if params:
                        for param in params:
                            if param.name == "IMAGE_NAME":
                                image_location = param.default
                    # save each taskRun inside the pipeline
                    task_runs = run.status.taskRuns
                    if task_runs:
                        for taskrun in task_runs:
                            if taskrun:
                                # taskResults come in list inside array format for some reason
                                props = taskrun[1].status.taskResults
                                if props:
                                    for prop in props:
                                        if prop.name == "url":
                                            repo_url = prop.value
                                        if prop.name == "commit":
                                            commit_sha = prop.value
                                        if prop.name == "IMAGE_DIGEST":
                                            image_hash = prop.value
                                        

                    metric.repo_url = repo_url
                    metric.commit_hash = commit_sha
                    metric.build_name = run.metadata.name
                    metric.build_config_name = run.metadata.labels["tekton.dev/pipeline"]
                    metric.namespace = run.metadata.namespace
                    labels = run.metadata.labels
                    metric.labels = json.loads(str(labels).replace("'", '"'))

                    metric.name = pipeline
                    metric.committer = "default"
                    metric.image_location = image_location
                    metric.image_hash = image_hash
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
                        self._commit_dict[metric.commit_hash] = metric.commit_timestamp
                    else:
                        metric.commit_timestamp = self._commit_dict[commit_sha]
                        logging.debug(
                            "Returning sha: %s, commit_timestamp: %s, from cache."
                            % (commit_sha, metric.commit_timestamp)
                        )
                    
                except Exception:
                    logging.error(
                        "Cannot collect metrics from run: %s" % (run.metadata.name)
                    )

                if metric:
                    logging.debug("Adding metric for pipeline %s" % pipeline)
                    metrics.append(metric)
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

#!/usr/bin/python3
import json
import logging
import os
import pelorus
import requests
import re
import time
from datetime import datetime
from jsonpath_ng import parse
from kubernetes import client

from openshift.dynamic import DynamicClient
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

REQUIRED_CONFIG = ['GITHUB_USER', 'GITHUB_TOKEN']

pelorus.load_kube_config()
k8s_config = client.Configuration()
k8s_client = client.api_client.ApiClient(configuration=k8s_config)
dyn_client = DynamicClient(k8s_client)


class CommitCollector(object):

    def __init__(self, username, token, namespaces, apps, git_api=None):
        self._username = username
        self._token = token
        self._namespaces = namespaces
        self._apps = apps
        self._git_api = git_api
        self.commit_dict = {}

    def collect(self):
        commit_metric = GaugeMetricFamily('github_commit_timestamp',
                                          'Commit timestamp', labels=['namespace', 'app', 'image_sha'])
        commit_metrics = self.generate_commit_metrics_list(self._namespaces)
        for my_metric in commit_metrics:
            logging.info("Namespace: %s, App: %s, Build: %s, Timestamp: %s"
                         % (
                             my_metric.namespace,
                             my_metric.name,
                             my_metric.build_name,
                             str(float(my_metric.commit_timestamp))
                         )
                         )
            commit_metric.add_metric([my_metric.namespace, my_metric.name, my_metric.image_hash],
                                     my_metric.commit_timestamp)
            yield commit_metric

    def match_image_id(self, replicationController, image_hash):
        for container in replicationController.spec.template.spec.containers:
            con_image = container.image
            image_tokens = con_image.split('@')
            if len(image_tokens) < 2:
                return False
            con_image_hash = image_tokens[1]
            if con_image_hash == image_hash:
                return True
        return False

    def convert_date_time_offset_to_timestamp(self, date_time):
        date_time = date_time[:-4]
        timestamp = datetime.strptime(date_time, '%Y-%m-%d %H:%M:%S %z')
        unixformattime = timestamp.timestamp()
        return unixformattime

    def convert_timestamp_to_date_time(self, timestamp):
        date_time = datetime(timestamp)
        return date_time.strftime('%Y-%m-%dT%H:%M:%SZ')

    def generate_commit_metrics_list(self, namespaces):

        if not namespaces:
            logging.info("No namespaces specified, watching all namespaces")
            v1_namespaces = dyn_client.resources.get(api_version='v1', kind='Namespace')
            namespaces = [namespace.metadata.name for namespace in v1_namespaces.get().items]
        else:
            logging.info("Watching namespaces: %s" % (namespaces))

        # Initialize metrics list
        metrics = []
        for namespace in namespaces:
            # Initialized variables
            builds = []
            apps = []
            builds_by_app = {}
            app_label = pelorus.get_app_label()
            logging.info("Searching for builds with label: %s in namespace: %s" % (app_label, namespace))

            v1_builds = dyn_client.resources.get(api_version='build.openshift.io/v1', kind='Build')
            # only use builds that have the app label
            builds = v1_builds.get(namespace=namespace, label_selector=app_label)

            # use a jsonpath expression to find all values for the app label
            jsonpath_str = "$['items'][*]['metadata']['labels']['" + str(app_label) + "']"
            jsonpath_expr = parse(jsonpath_str)

            found = jsonpath_expr.find(builds)

            apps = [match.value for match in found]

            if not apps:
                continue
            # remove duplicates
            apps = list(dict.fromkeys(apps))
            builds_by_app = {}

            for app in apps:
                builds_by_app[app] = list(filter(lambda b: b.metadata.labels[app_label] == app, builds.items))

            metrics += self.get_metrics_from_apps(builds_by_app, namespace)

        return metrics

    # get_metrics_from_apps - expects a sorted array of build data sorted by app label
    def get_metrics_from_apps(self, apps, namespace):
        metrics = []
        for app in apps:

            builds = apps[app]

            jenkins_builds = list(filter(lambda b: b.spec.strategy.type == 'JenkinsPipeline', builds))
            code_builds = list(filter(lambda b: b.spec.strategy.type in ['Source', 'Binary'], builds))

            # assume for now that there will only be one repo/branch per app
            # For jenkins pipelines, we need to grab the repo data
            # then find associated s2i/docker builds from which to pull commit & image data
            repo_url = None
            if jenkins_builds:
                # we will default to the repo listed in '.spec.source.git'
                repo_url = jenkins_builds[0].spec.source.git.uri

                # however, in cases where the Jenkinsfile and source code are separate, we look for params
                git_repo_regex = re.compile(r"(\w+://)(.+@)*([\w\d\.]+)(:[\d]+){0,1}/*(.*)")
                for env in jenkins_builds[0].spec.strategy.jenkinsPipelineStrategy.env:
                    result = git_repo_regex.match(env.value)
                    if result:
                        repo_url = env.value

            for build in code_builds:
                try:
                    metric = self.get_metric_from_build(build, app, namespace, repo_url)
                except Exception:
                    logging.error("Cannot collect metrics from build: %s" % (build.metadata.name))

                if metric:
                    metrics.append(metric)
        return metrics

    def get_metric_from_build(self, build, app, namespace, repo_url):
        try:

            metric = CommitTimeMetric(app, self._git_api)

            if build.spec.source.git:
                repo_url = build.spec.source.git.uri

            metric.repo_url = repo_url
            commit_sha = build.spec.revision.git.commit
            metric.build_name = build.metadata.name
            metric.build_config_name = build.metadata.labels.buildconfig
            metric.namespace = build.metadata.namespace
            labels = build.metadata.labels
            metric.labels = json.loads(str(labels).replace("\'", "\""))

            metric.commit_hash = commit_sha
            metric.name = app + '-' + commit_sha
            metric.commiter = build.spec.revision.git.author.name
            metric.image_location = build.status.outputDockerImageReference
            metric.image_hash = build.status.output.to.imageDigest
            # Check the cache for the commit_time, if not call the API
            metric_ts = self.commit_dict.get(commit_sha)
            if metric_ts is None:
                logging.debug("sha: %s, commit_timestamp not found in cache, executing API call." % (commit_sha))
                metric.getCommitTime()
                # If commit time is None, then we could not get the value from the API
                # This is due to calling a non Github API.
                if metric.commit_time is None:
                    return None
                # Add the timestamp to the cache
                self.commit_dict[metric.commit_hash] = metric.commit_timestamp
            else:
                metric.commit_timestamp = self.commit_dict[commit_sha]
                logging.debug("Returning sha: %s, commit_timestamp: %s, from cache." % (
                    commit_sha, metric.commit_timestamp))

            return metric

        except Exception as e:
            logging.warning("Build %s/%s in app %s is missing required attributes to collect data. Skipping."
                            % (namespace, build.metadata.name, app))
            logging.debug(e, exc_info=True)
            return None


class CommitTimeMetric:
    _prefix_pattern = "https://%s/repos/"
    _defaultapi = "api.github.com"
    _prefix = _prefix_pattern % _defaultapi
    _suffix = "/commits/"

    def __init__(self, app_name, _gitapi=None):
        self.name = app_name
        self.labels = None
        self.repo_url = None
        self.commiter = None
        self.commit_hash = None
        self.commit_time = None
        self.commit_timestamp = None
        self.build_name = None
        self.build_config_name = None
        self.image_location = None
        self.image_name = None
        self.image_tag = None
        self.image_hash = None
        if _gitapi is not None and len(_gitapi) > 0:
            logging.info("Using non-default GitHub API: %s" % (_gitapi))
            self._prefix = self._prefix_pattern % _gitapi

    def getCommitTime(self):
        myurl = self.repo_url
        url_tokens = myurl.split("/")
        url = self._prefix + url_tokens[3] + "/" + url_tokens[4].split(".")[0] + self._suffix + self.commit_hash
        response = requests.get(url, auth=(username, token))
        if response.status_code != 200:
            # This will occur when trying to make an API call to non-Github
            logging.warning("Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s" % (
                self.build_name, self.commit_hash, url_tokens[2], str(response.status_code)))
        else:
            commit = response.json()
            try:
                self.commit_time = commit['commit']['committer']['date']
                self.commit_timestamp = pelorus.convert_date_time_to_timestamp(self.commit_time)
            except Exception:
                logging.error("Failed processing commit time for build %s" % self.build_name, exc_info=True)
                logging.debug(commit)
                raise


if __name__ == "__main__":
    pelorus.check_required_config(REQUIRED_CONFIG)
    username = os.environ.get('GITHUB_USER')
    token = os.environ.get('GITHUB_TOKEN')
    git_api = os.environ.get('GITHUB_API')
    namespaces = None
    if os.environ.get('NAMESPACES') is not None:
        namespaces = [proj.strip() for proj in os.environ.get('NAMESPACES').split(",")]
    apps = None
    start_http_server(8080)
    REGISTRY.register(CommitCollector(username, token, namespaces, apps, git_api))
    while True:
        time.sleep(1)

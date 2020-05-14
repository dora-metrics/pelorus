#!/usr/bin/python3
import json
import logging
import os
import requests
import re
import urllib3
import time
import yaml
from datetime import datetime, timezone
from jsonpath_ng import jsonpath, parse
from kubernetes import client, config
from lib_pelorus import loader
from openshift.dynamic import DynamicClient
from prometheus_client import start_http_server
from prometheus_client.core import CounterMetricFamily,InfoMetricFamily,GaugeMetricFamily, REGISTRY


loader.load_kube_config()
k8s_config = client.Configuration()
k8s_client = client.api_client.ApiClient(configuration=k8s_config)
dyn_client = DynamicClient(k8s_client)

class CommitCollector(object):
    _prefix = "https://api.github.com/repos/"
    _suffix = "/commits"
    def __init__(self, username, token, namespaces, apps):
        self._username = username
        self._token = token
        self._namespaces = namespaces
        self._apps = apps
    def collect(self):
        ld_metric = GaugeMetricFamily('github_commit_timestamp', 'Commit timestamp', labels=['namespace', 'app', 'image_sha'])
        ld_metrics = generate_ld_metrics_list(self._namespaces)
        for my_metric in ld_metrics:
            logging.info("Namespace: %s, App: %s, Build: %s" % (my_metric.namespace, my_metric.name, my_metric.build_name))
            ld_metric.add_metric([my_metric.namespace, my_metric.name, my_metric.image_hash], my_metric.commit_timestamp)
            yield ld_metric

class CommitTimeMetric:
    def __init__(self, app_name):
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
    def getCommitTime(self):
        _prefix = "https://api.github.com/repos/"
        _suffix = "/commits/"
        myurl = self.repo_url
        url_tokens = myurl.split("/")
        url = _prefix + url_tokens[3] + "/" +url_tokens[4].split(".")[0] +_suffix+self.commit_hash
        response = requests.get(url, auth=(username, token))
        commit = response.json()
        try:
            self.commit_time = commit['commit']['committer']['date']
            self.commit_timestamp = loader.convert_date_time_to_timestamp(self.commit_time)
        except KeyError:
            logging.error("Failed processing commit time for build %s" % self.build_name, exc_info=True)
            logging.debug(commit)

def match_image_id(replicationController, image_hash):
    for container in replicationController.spec.template.spec.containers:
        con_image = container.image
        image_tokens = con_image.split('@')
        if len(image_tokens) < 2:
            return False
        con_image_hash = image_tokens[1]
        if con_image_hash == image_hash:
            return True
    return False

def convert_date_time_offset_to_timestamp(date_time):
    date_time = date_time[:-4]
    timestamp = datetime.strptime(date_time, '%Y-%m-%d %H:%M:%S %z')
    unixformattime = timestamp.timestamp()
    return unixformattime

def convert_timestamp_to_date_time(timestamp):
    date_time = datetime(timestamp)
    return datetime.strftime('%Y-%m-%dT%H:%M:%SZ')


def generate_ld_metrics_list(namespaces):

    metrics = []
    if not namespaces:
        logging.info("No namespaces specified, watching all namespaces\n")
        v1_namespaces = dyn_client.resources.get(api_version='v1', kind='Namespace')
        namespaces = [ namespace.metadata.name for namespace in v1_namespaces.get().items ]
    else:
        logging.info("Watching namespaces: %s\n" %(namespaces))


    for namespace in namespaces:
        # Initialized variables
        builds = []
        build = {}
        apps = []
        builds_by_app = {}
        jenkins_builds = []
        code_builds = []

        v1_builds = dyn_client.resources.get(api_version='build.openshift.io/v1',  kind='Build')
        # only use builds that have the app label
        builds = v1_builds.get(namespace=namespace, label_selector=loader.get_app_label())


        # use a jsonpath expression to find all values for the app label
        jsonpath_str = "$['items'][*]['metadata']['labels']['" + str(loader.get_app_label()) + "']"
        jsonpath_expr = parse(jsonpath_str)


        found = jsonpath_expr.find(builds)

        apps = [match.value for match in found]


        if not apps:
            continue
        # remove duplicates
        apps = list(dict.fromkeys(apps))
        builds_by_app = {}

        for app in apps:
            builds_by_app[app] = list(filter(lambda b: b.metadata.labels[loader.get_app_label()] == app, builds.items))

        for app in builds_by_app:

            builds = builds_by_app[app]

            # jsonpath to get commits
            jsonpath_expr = parse('*.spec.revision.git.commit')
            commits = [match.value for match in jsonpath_expr.find(builds)]
            jenkins_builds = list(filter(lambda b: b.spec.strategy.type == 'JenkinsPipeline', builds))
            code_builds = list(filter(lambda b: b.spec.strategy.type in ['Source', 'Binary'], builds))

            # assume for now that there will only be one repo/branch per app
            # For jenkins pipelines, we need to grab the repo data
            # then find associated s2i/docker builds from which to pull commit & image data

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
                    metric = CommitTimeMetric(app)

                    if build.spec.source.git:
                        repo_url = build.spec.source.git.uri

                    if "github.com" not in repo_url:
                        logging.warning("Only GitHub repos are currently supported. Skipping build %s" % build.metadata.name)

                    metric.repo_url = repo_url
                    
                    metric.build_name=build.metadata.name
                    metric.build_config_name = build.metadata.labels.buildconfig
                    metric.namespace = build.metadata.namespace
                    labels = build.metadata.labels
                    metric.labels = json.loads(str(labels).replace("\'", "\""))
                    
                    metric.commit_hash = build.spec.revision.git.commit
                    metric.name = app + '-' + build.spec.revision.git.commit
                    metric.commiter = build.spec.revision.git.author.name
                    metric.image_location = build.status.outputDockerImageReference
                    metric.image_hash = build.status.output.to.imageDigest
                    metric.getCommitTime()
                    metrics.append(metric)

                except AttributeError as e:
                    logging.warning("Build %s/%s in app %s is missing required attributes to collect data. Skipping." % (namespace, build.metadata.name, app))
                    logging.debug(e, exc_info=True)

    return metrics

if __name__ == "__main__":
    username = os.environ.get('GITHUB_USER')
    token = os.environ.get('GITHUB_TOKEN')
    namespaces = None
    if os.environ.get('NAMESPACES') is not None:
        namespaces = [ proj.strip() for proj in os.environ.get('NAMESPACES').split(",") ]
    apps = None
    start_http_server(8080)
    REGISTRY.register(CommitCollector(username, token, namespaces, apps))
    while True:
        time.sleep(1)


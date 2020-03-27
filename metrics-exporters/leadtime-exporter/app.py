import json
import os
import pprint
import requests
import re
import urllib3
import sys
import time
import yaml
from datetime import datetime, timezone
from jsonpath_ng import jsonpath
from jsonpath_ng.ext import parse
from kubernetes import client, config
from openshift.dynamic import DynamicClient
from prometheus_client import start_http_server
from prometheus_client.core import CounterMetricFamily,InfoMetricFamily,GaugeMetricFamily, REGISTRY

class CommitCollector(object):
    _prefix = "https://api.github.com/repos/"
    _suffix = "/commits"
    def __init__(self, username, token, projects, apps):
        self._username = username
        self._token = token
        self._projects = projects
        self._apps = apps
    def collect(self):
        ld_metric = GaugeMetricFamily('github_commit_timestamp', 'Commit timestamp', labels=['namespace', 'app', 'build', 'commit_hash'])
        ld_metrics = generate_ld_metrics_list(projects)
        for my_metric in ld_metrics:
            print("Namespace: ", my_metric.namespace, ", App: ", my_metric.name, ", Build: ", my_metric.build_name)
            ld_metric.add_metric([my_metric.namespace, my_metric.name, my_metric.build_name, my_metric.commit_hash], my_metric.commit_timestamp)
            yield ld_metric

class CommitTimeMetric:
    def __init__(self, app_name):
        self.name = app_name
        self.labels = None
        self.repo_url = None
        self.commiter = None
        self.commit_hash = None
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
        self.commit_timestamp = convert_date_time_to_timestamp(commit['commit']['committer']['date'])

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

def convert_date_time_to_timestamp(date_time):
    timestamp = datetime.strptime(date_time, '%Y-%m-%dT%H:%M:%SZ')
    unixformattime = timestamp.replace(tzinfo=timezone.utc).timestamp()
    return unixformattime       

def convert_timestamp_to_date_time(timestamp):
    date_time = datetime(timestamp)
    return datetime.strftime('%Y-%m-%dT%H:%M:%SZ')

def get_app_label():
    return os.getenv('APP_LABEL', 'application')

def generate_ld_metrics_list(projects):

    urllib3.disable_warnings()
    if "OPENSHIFT_BUILD_NAME" in os.environ:
        config.load_incluster_config()
        file_namespace = open(
            "/run/secrets/kubernetes.io/serviceaccount/namespace", "r"
        )
        if file_namespace.mode == "r":
            namespace = file_namespace.read()
            print("namespace: %s\n" %(namespace))
    else:
        config.load_kube_config()

    k8s_config = client.Configuration()
    k8s_client = client.api_client.ApiClient(configuration=k8s_config)
    dyn_client = DynamicClient(k8s_client)

    metrics = []
    if not projects:
        print("No projects specified, watching all projects\n")
        v1_projects = dyn_client.resources.get(api_version='project.openshift.io/v1', kind='Project')
        projects = [ project.metadata.name for project in v1_projects.get().items ]
    else:
        print("Watching projects: %s\n" %(projects))

    jsonpath_str = 'items[?metadata.labels.%s].metadata.labels.%s' % (get_app_label(), get_app_label())
    jsonpath_expr = parse(jsonpath_str)
    print("JSONPATH: " + jsonpath_str)

    for project in projects:
        # Initialized variables
        builds = []
        build = {}
        apps = []
        builds_by_app = {}
        jenkins_builds = []
        code_builds = []

        print("Checking namespace %s" % project)
        v1_builds = dyn_client.resources.get(api_version='build.openshift.io/v1',  kind='Build')
        builds = v1_builds.get(namespace=project)
        # use a jsonpath expression to find all values for the app label
        apps = [match.value for match in jsonpath_expr.find(builds)]

        print("Apps: " + pprint.pformat(apps))

        if not apps:
            continue
        # remove duplicates
        apps = list(dict.fromkeys(apps))
        builds_by_app = {}

        print("Found builds for apps: ")
        pprint.pprint(apps)

        for app in apps:
            builds_by_app[app] = list(filter(lambda b: b.metadata.labels[get_app_label()] == app, builds.items))

        #pprint.pprint(builds_by_app, indent=2, depth=2)

        #v1_replicationControllers = dyn_client.resources.get(api_version='v1',  kind='ReplicationController')
        #replicationControllers = v1_replicationControllers.get(namespace=project)

        for app in builds_by_app:

            builds = builds_by_app[app]

            print("App: %s" % app)
            #print("Builds: ")
            #pprint.pprint(builds, depth=1)
            
            # jsonpath to get commits
            jsonpath_expr = parse('*.spec.revision.git.commit')
            commits = [match.value for match in jsonpath_expr.find(builds)]
            jenkins_builds = list(filter(lambda b: b.spec.strategy.type == 'JenkinsPipeline', builds))
            code_builds = list(filter(lambda b: b.spec.strategy.type in ['Source', 'Binary'], builds))

            # assume for now that there will only be one repo/branch per app
            # For jenkins pipelines, we need to grab the repo data
            # then find associated s2i/docker builds from which to pull commit & image data

            if jenkins_builds:
                #print(jenkins_builds)
                # we will default to the repo listed in '.spec.source.git'
                #pprint.pprint(jenkins_builds, depth=1)

                repo_url = jenkins_builds[0].spec.source.git.uri

                # however, in cases where the Jenkinsfile and source code are separate, we look for params
                git_repo_regex = re.compile(r"(\w+://)(.+@)*([\w\d\.]+)(:[\d]+){0,1}/*(.*)")
                for env in jenkins_builds[0].spec.strategy.jenkinsPipelineStrategy.env:
                    result = git_repo_regex.match(env.value)
                    if result:
                        repo_url = env.value

            for build in code_builds:

                metric = CommitTimeMetric(app)
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

    return metrics

if __name__ == "__main__":
    username = os.environ.get('GITHUB_USER')
    token = os.environ.get('GITHUB_TOKEN')
    projects = None
    if os.environ.get('PROJECTS') is not None:
        projects = [ proj.strip() for proj in os.environ.get('PROJECTS').split(",") ]
    apps = None
    start_http_server(8080)
    REGISTRY.register(CommitCollector(username, token, projects, apps))
    while True:
        time.sleep(1)


import yaml
import json
import time
import urllib3
import requests
import os
from datetime import datetime, timezone
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
            print("Namespace: ", my_metric.namespace, ", App: ", my_metric.app_name, ", Build: ", my_metric.build_name)
            ld_metric.add_metric([my_metric.namespace, my_metric.app_name, my_metric.build_name, my_metric.commit_hash], my_metric.lead_time)
            yield ld_metric
class mdt_metric:
    def __init__(self, app_name):
        self.app_name = app_name
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
        self.deployment_config_name = None
        self.deployment_timestamp = None
        self.lead_time = 0
    def getCommitTime(self):
        _prefix = "https://api.github.com/repos/"
        _suffix = "/commits/"
        myurl = self.repo_url
        url_tokens = myurl.split("/")
        url = _prefix + url_tokens[3] + "/" +url_tokens[4].split(".")[0] +_suffix+self.commit_hash
        response = requests.get(url, auth=(username, token))
#        print(username, token)
        commit = response.json()
#        print(commit)
        self.commit_time = commit['commit']['committer']['date']
        self.commit_timestamp = convert_date_time_to_timestamp(self.commit_time)
    def calculate_lead_time(self):
        self.lead_time = self.deployment_timestamp - self.commit_timestamp

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
    if projects == None:
        v1_projects = dyn_client.resources.get(api_version='project.openshift.io/v1', kind='Project')
        projects = [ project.metadata.name for project in v1_projects.get().items ]

    for project in projects:    
        v1_builds = dyn_client.resources.get(api_version='v1',  kind='Build')
        builds = v1_builds.get(namespace=project)

        v1_replicationControllers = dyn_client.resources.get(api_version='v1',  kind='ReplicationController')
        replicationControllers = v1_replicationControllers.get(namespace=project)

        print ('Builds Count = ' , len(builds.items))
        for build in builds.items:
            if build['spec']['source']['type'] == 'Git':
                if build['status']['phase'] =='Complete':
                    app_name = build.metadata.labels.app
                    metric = mdt_metric(app_name)
                    metric.build_name=build.metadata.name
                    metric.build_config_name = build.metadata.labels.buildconfig                    
                    metric.namespace = build.metadata.namespace
                    labels = build.metadata.labels
                    metric.labels = json.loads(str(labels).replace("\'", "\""))
                    metric.repo_url = build.spec.source.git.uri
                    metric.commit_hash = build.spec.revision.git.commit
                    metric.commiter = build.spec.revision.git.author.name
                    metric.image_location = build.status.outputDockerImageReference
                    metric.image_hash = build.status.output.to.imageDigest
                    rcs = [rc for rc in replicationControllers.items if match_image_id(rc, metric.image_hash) ]
                    metric.replication_controller_name=rcs[0].metadata.name
                    metric.deployment_time = rcs[0].metadata.annotations['openshift.io/deployer-pod.completed-at']
                    metric.deployment_config_name = rcs[0].metadata.annotations['openshift.io/deployment-config.name']
                    metric.deployment_timestamp = convert_date_time_offset_to_timestamp(metric.deployment_time)
                    metric.getCommitTime()
                    metric.calculate_lead_time()
                    metrics.append(metric)
    return metrics

if __name__ == "__main__":
    username = os.environ.get('GITHUB_USER')
    token = os.environ.get('GITHUB_TOKEN')
    projects = None
    if os.environ.get('PROJECTS') is not None:
        projects = [ proj.strip() for proj in os.environ.get('PROJECTS').split(",") ]
    apps = None
    REGISTRY.register(CommitCollector(username, token, projects, apps))
    start_http_server(9118)
    while True: time.sleep(1)


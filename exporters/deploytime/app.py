import os
import re
import time
from jsonpath_ng import jsonpath, parse
from kubernetes import client
from lib import loader
from openshift.dynamic import DynamicClient
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

loader.load_kube_config()
k8s_config = client.Configuration()
k8s_client = client.api_client.ApiClient(configuration=k8s_config)
dyn_client = DynamicClient(k8s_client)


class DeployTimeCollector(object):
    def __init__(self, projects):
        self._projects = projects
    def collect(self):
        metric = GaugeMetricFamily('deploy_timestamp', 'Deployment timestamp', labels=['namespace', 'app', 'image_sha'])
        metrics = generate_metrics(self._projects)
        for m in metrics:
            print("Namespace: ", m.namespace, ", App: ", m.name, ", Image: ", m.image_sha)
            metric.add_metric([m.namespace, m.name, m.image_sha, m.deploy_time], loader.convert_date_time_to_timestamp(m.deploy_time))
            yield(metric)

class DeployTimeMetric:
    def __init__(self, name, ns):
        self.name = name
        self.namespace = ns

        self.labels = None
        self.deploy_time = None
        self.image_sha = None

def image_sha(img_url):
    sha_regex = re.compile(r"sha256:.*")
    return sha_regex.search(img_url).group()

def generate_metrics(projects):

    metrics = []

    if not projects:
        print("No projects specified, watching all projects\n")
        v1_projects = dyn_client.resources.get(api_version='project.openshift.io/v1', kind='Project')
        projects = [ project.metadata.name for project in v1_projects.get().items ]
    else:
        print("Watching projects: %s\n" %(projects))

    for project in projects:
        v1_replicationcontrollers = dyn_client.resources.get(api_version='v1', kind='ReplicationController')
        replicationcontrollers = v1_replicationcontrollers.get(namespace=project, label_selector=loader.get_app_label())

        for rc in replicationcontrollers.items:
            images = [image_sha(c.image) for c in rc.spec.template.spec.containers]

            # Since a commit will be built into a particular image and there could be multiple containers (images) per pod,
            #   we will push one metric per image/container in the pod template
            for i in images:
                metric = DeployTimeMetric(rc.metadata.name, project)
                metric.labels = rc.metadata.labels
                metric.deploy_time = rc.metadata.creationTimestamp            
                metric.image_sha = i
                metrics.append(metric)

    return metrics

if __name__ == "__main__":
    projects = None
    if os.environ.get('PROJECTS') is not None:
        projects = [ proj.strip() for proj in os.environ.get('PROJECTS').split(",") ]
    start_http_server(8080)
    REGISTRY.register(DeployTimeCollector(projects))
    while True:
        time.sleep(1)

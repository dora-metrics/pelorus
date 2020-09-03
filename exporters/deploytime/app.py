import logging
import os
import re
import pelorus
import time
from kubernetes import client
from openshift.dynamic import DynamicClient
from openshift.dynamic.exceptions import ResourceNotFoundError
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

pelorus.load_kube_config()
k8s_config = client.Configuration()
k8s_client = client.api_client.ApiClient(configuration=k8s_config)
dyn_client = DynamicClient(k8s_client)


class DeployTimeCollector(object):
    def __init__(self, namespaces):
        self._namespaces = namespaces

    def collect(self):
        metric = GaugeMetricFamily('deploy_timestamp', 'Deployment timestamp', labels=['namespace', 'app', 'image_sha'])
        metrics = generate_metrics(self._namespaces)
        for m in metrics:
            print("Namespace: ", m.namespace, ", App: ", m.name, ", Image: ", m.image_sha)
            metric.add_metric([m.namespace, m.name, m.image_sha, m.deploy_time],
                              pelorus.convert_date_time_to_timestamp(m.deploy_time))
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
    try:
        return sha_regex.search(img_url).group()
    except AttributeError:
        logging.debug("Skipping unresolved image reference: %s" % img_url)
        return None


def generate_metrics(namespaces):

    metrics = []

    if not namespaces:
        print("No namespaces specified, watching all namespaces\n")
        v1_namespaces = dyn_client.resources.get(api_version='v1', kind='Namespace')
        namespaces = [namespace.metadata.name for namespace in v1_namespaces.get(
            label_selector=pelorus.get_prod_label()).items]
    else:
        print("Watching namespaces: %s\n" % (namespaces))

    for namespace in namespaces:
        replicas = []

        # Process ReplicationControllers for DeploymentConfigs
        replicas = get_replicas('v1', 'ReplicationController', namespace)

        # Process ReplicaSets from apps/v1 api version for Deployments
        replicas = replicas + get_replicas('apps/v1', 'ReplicaSet', namespace)

        # Process ReplicaSets from extentions/v1beta1 api version for Deployments
        replicas = replicas + get_replicas('extensions/v1beta1x', 'ReplicaSet', namespace)

        for rc in replicas:
            images = [image_sha(c.image) for c in rc.spec.template.spec.containers]
            print("IMAGE" + str(images))

            # Since a commit will be built into a particular image and there could be multiple
            # containers (images) per pod, we will push one metric per image/container in the
            # pod template
            for i in images:
                if i is not None:
                    metric = DeployTimeMetric(rc.metadata.name, namespace)
                    metric.labels = rc.metadata.labels
                    metric.deploy_time = rc.metadata.creationTimestamp
                    metric.image_sha = i
                    metrics.append(metric)

    return metrics


def get_replicas(apiVersion, objectName, namespace):
    replicas = []
    # Process ReplicaSets from apps/v1 api version for Deployments
    try:
        apiResource = dyn_client.resources.get(api_version=apiVersion, kind=objectName)
        replicationobjects = apiResource.get(namespace=namespace,
                                             label_selector=pelorus.get_app_label())
        replicas = replicas + replicationobjects.items
    except ResourceNotFoundError:
        logging.debug("API Object not found for version: %s object:%s" , apiVersion, objectName)
        pass
    return replicas


if __name__ == "__main__":
    namespaces = None
    if os.environ.get('NAMESPACES') is not None:
        namespaces = [proj.strip() for proj in os.environ.get('NAMESPACES').split(",")]
    start_http_server(8080)
    REGISTRY.register(DeployTimeCollector(namespaces))
    while True:
        time.sleep(1)

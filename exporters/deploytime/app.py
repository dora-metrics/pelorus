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
        logging.info("collect: start")
        metric = GaugeMetricFamily('deploy_timestamp', 'Deployment timestamp', labels=['namespace', 'app', 'image_sha'])
        metrics = generate_metrics(self._namespaces)
        for m in metrics:
            logging.info("Namespace: %s, App: %s, Image: %s", m.namespace, m.name, m.image_sha)
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
    pods = []
    pod_replica_dict = {}

    logging.info("generate_metrics: start")

    v1_pods = dyn_client.resources.get(api_version='v1', kind='Pod')
    if not namespaces:
        logging.info("No namespaces specified, watching all namespaces")
    else:
        logging.info("Wwtching namespaces %s", namespaces)

    pods = v1_pods.get(label_selector=pelorus.get_app_label(), field_selector='status.phase=Running').items

    replicas_dict = {}
    # Process ReplicationControllers for DeploymentConfigs
    get_replicas('v1', 'ReplicationController', replicas_dict)

    # Process ReplicaSets from apps/v1 api version for Deployments
    get_replicas('apps/v1', 'ReplicaSet', replicas_dict)

    # Process ReplicaSets from extentions/v1beta1 api version for Deployments
    get_replicas('extensions/v1beta1', 'ReplicaSet', replicas_dict)

    for pod in pods:
        if not namespaces or (pod.metadata.namespace in namespaces):
            logging.info("Getting Replicas for pod: %s", pod.metadata.name)
            ownerRefs = pod.metadata.ownerReferences
            namespace = pod.metadata.namespace

            for ownerRef in ownerRefs:
                if ownerRef.kind in ['ReplicaSet', 'ReplicationController'] and not pod_replica_dict.get(ownerRef.name):

                    logging.info("Getting Replica ownerRef: %s, %s",  ownerRef.name, ownerRef.kind)

                    # Process ReplicationControllers for DeploymentConfigs
                    rc = replicas_dict[ownerRef.name]

                    if rc:
                        pod_replica_dict[rc.metadata.name] = "DONE"
                        images = [image_sha(c.image) for c in pod.spec.containers]

                        # Since a commit will be built into a particular image and there could be multiple
                        # containers (images) per pod, we will push one metric per image/container in the
                        # pod template
                        for i in images:
                            if i is not None:
                                metric = DeployTimeMetric(rc.metadata.name, namespace)
                                metric.labels = rc.metadata.labels
                                metric.deploy_time = rc.metadata.creationTimestamp
                                metric.image_sha = i
                                metric.namespace = namespace
                                metrics.append(metric)

    return metrics


def get_replicas(apiVersion, objectName, replicas):
    # Process ReplicaSets from apps/v1 api version for Deployments
    try:
        apiResource = dyn_client.resources.get(api_version=apiVersion, kind=objectName)
        replicationobjects = apiResource.get(label_selector=pelorus.get_app_label())
        for replica in replicationobjects.items:
            replicas[replica.metadata.name] = replica
    except ResourceNotFoundError:
        logging.debug("API Object not found for version: %s object: %s", apiVersion, objectName)
        pass


if __name__ == "__main__":
    namespaces = None
    if os.environ.get('NAMESPACES') is not None:
        namespaces = [proj.strip() for proj in os.environ.get('NAMESPACES').split(",")]
    start_http_server(8080)
    REGISTRY.register(DeployTimeCollector(namespaces))
    while True:
        time.sleep(1)

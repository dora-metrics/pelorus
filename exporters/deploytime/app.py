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

supported_replica_objects = ['ReplicaSet', 'ReplicationController']


class DeployTimeCollector(object):
    def __init__(self, namespaces):
        self._namespaces = namespaces

    def collect(self):
        logging.info("collect: start")
        metric = GaugeMetricFamily('deploy_timestamp', 'Deployment timestamp', labels=['namespace', 'app', 'image_sha'])
        metrics = generate_metrics(self._namespaces)
        for m in metrics:
            logging.info("Collected deploy_timestamp{namespace=%s, app=%s, image=%s} %s" %
                         (m.namespace, m.name, m.image_sha, pelorus.convert_date_time_to_timestamp(m.deploy_time))
                         )
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
        img_url_split = img_url.split(':')
        if len(img_url_split) > 1:
            truncated_img_url = img_url_split[1]
            image_regex = re.compile(r"[a-f0-9]{5,40}")
            m = image_regex.search(truncated_img_url)
            if m:
                return m.group()
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
        logging.info("Watching namespaces %s", namespaces)

    pods = v1_pods.get(label_selector=pelorus.get_app_label(), field_selector='status.phase=Running').items

    replicas_dict = {}
    # Process ReplicationControllers for DeploymentConfigs
    replicas_dict = get_replicas('v1', 'ReplicationController')

    # Process ReplicaSets from apps/v1 api version for Deployments
    replicas_dict.update(get_replicas('apps/v1', 'ReplicaSet'))

    # Process ReplicaSets from extentions/v1beta1 api version for Deployments
    replicas_dict.update(get_replicas('extensions/v1beta1', 'ReplicaSet'))

    for pod in pods:
        if (not namespaces or (pod.metadata.namespace in namespaces)) and pod.metadata.ownerReferences:
            logging.debug("Getting Replicas for pod: %s in namespace: %s", pod.metadata.name, pod.metadata.namespace)
            ownerRefs = pod.metadata.ownerReferences
            namespace = pod.metadata.namespace

            # use the replica controller/replicasets to get deploy timestamp.  The ownerRef of pod is used to get
            # replication controller.  A dictionary is used to handle dups when multiple pods are running.
            for ownerRef in ownerRefs:
                if (ownerRef.kind in supported_replica_objects and
                   not pod_replica_dict.get(namespace + "/" + ownerRef.name)):

                    logging.debug("Getting replica: %s, kind: %s, namespace: %s",
                                  ownerRef.name, ownerRef.kind, namespace)

                    if replicas_dict.get(namespace + "/" + ownerRef.name):
                        rc = replicas_dict.get(namespace + "/" + ownerRef.name)
                        pod_replica_dict[namespace + "/" + ownerRef.name] = "DONE"
                        images = [image_sha(c.image) for c in pod.spec.containers]

                        # Since a commit will be built into a particular image and there could be multiple
                        # containers (images) per pod, we will push one metric per image/container in the
                        # pod template
                        for i in images:
                            if i is not None:
                                metric = DeployTimeMetric(rc.metadata.labels[pelorus.get_app_label()], namespace)
                                metric.labels = rc.metadata.labels
                                metric.deploy_time = rc.metadata.creationTimestamp
                                metric.image_sha = i
                                metric.namespace = namespace
                                metrics.append(metric)

    return metrics


def get_replicas(apiVersion, objectName):
    # Process Replicas for given Api Version and Object type (ReplicaSet or ReplicationController)
    replicas = {}
    try:
        apiResource = dyn_client.resources.get(api_version=apiVersion, kind=objectName)
        replicationobjects = apiResource.get(label_selector=pelorus.get_app_label())
        for replica in replicationobjects.items:
            replicas[replica.metadata.namespace + "/" + replica.metadata.name] = replica
    except ResourceNotFoundError:
        logging.debug("API Object not found for version: %s object: %s", apiVersion, objectName)
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

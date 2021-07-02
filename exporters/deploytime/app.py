import logging
import os
import re
import time
from typing import Iterable, Optional

import attr
from kubernetes import client
from openshift.dynamic import DynamicClient
from openshift.dynamic.exceptions import ResourceNotFoundError
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY, GaugeMetricFamily

import pelorus

supported_replica_objects = ["ReplicaSet", "ReplicationController"]

# A NamespaceSpec is either a list of namespaces to restrict the search to,
# or None to include all namespaces.
# An empty list technically means search nothing-- you probably don't want this.
NamespaceSpec = Optional[list[str]]


class DeployTimeCollector:
    def __init__(self, namespaces: NamespaceSpec, client: DynamicClient):
        self._namespaces = namespaces
        self.client = client

    def collect(self) -> Iterable[GaugeMetricFamily]:
        logging.info("collect: start")
        metric = GaugeMetricFamily(
            "deploy_timestamp",
            "Deployment timestamp",
            labels=["namespace", "app", "image_sha"],
        )
        metrics = generate_metrics(self._namespaces, self.client)
        for m in metrics:
            logging.info(
                "Collected deploy_timestamp{namespace=%s, app=%s, image=%s} %s"
                % (
                    m.namespace,
                    m.name,
                    m.image_sha,
                    pelorus.convert_date_time_to_timestamp(m.deploy_time),
                )
            )
            metric.add_metric(
                [m.namespace, m.name, m.image_sha, m.deploy_time],
                pelorus.convert_date_time_to_timestamp(m.deploy_time),
            )
            yield (metric)


@attr.define(kw_only=True)
class DeployTimeMetric:
    name: str
    namespace: str
    labels: dict[str, str]
    deploy_time: object
    image_sha: str


def image_sha(img_url: str) -> Optional[str]:
    sha_regex = re.compile(r"sha256:.*")
    try:
        return sha_regex.search(img_url).group()
    except AttributeError:
        logging.debug("Skipping unresolved image reference: %s" % img_url)
        return None


def generate_metrics(
    namespaces: NamespaceSpec, dyn_client: DynamicClient
) -> list[DeployTimeMetric]:

    metrics = []
    pods = []
    pod_replica_dict = {}

    logging.info("generate_metrics: start")

    v1_pods = dyn_client.resources.get(api_version="v1", kind="Pod")
    if not namespaces:
        logging.info("No namespaces specified, watching all namespaces")
    else:
        logging.info("Watching namespaces %s", namespaces)

    pods = v1_pods.get(
        label_selector=pelorus.get_app_label(), field_selector="status.phase=Running"
    ).items

    replicas_dict = {}
    # Process ReplicationControllers for DeploymentConfigs
    replicas_dict = get_replicas(dyn_client, "v1", "ReplicationController")

    # Process ReplicaSets from apps/v1 api version for Deployments
    replicas_dict.update(get_replicas(dyn_client, "apps/v1", "ReplicaSet"))

    # Process ReplicaSets from extentions/v1beta1 api version for Deployments
    replicas_dict.update(get_replicas(dyn_client, "extensions/v1beta1", "ReplicaSet"))

    for pod in pods:
        if (
            not namespaces or (pod.metadata.namespace in namespaces)
        ) and pod.metadata.ownerReferences:
            logging.debug(
                "Getting Replicas for pod: %s in namespace: %s",
                pod.metadata.name,
                pod.metadata.namespace,
            )
            ownerRefs = pod.metadata.ownerReferences
            namespace = pod.metadata.namespace

            # use the replica controller/replicasets to get deploy timestame.  The ownerRef of pod is used to get
            # replicaiton controller.  A dictionary is used to handle dups when multiple pods are running.
            for ownerRef in ownerRefs:
                if (
                    ownerRef.kind in supported_replica_objects
                    and not pod_replica_dict.get(namespace + "/" + ownerRef.name)
                ):

                    logging.debug(
                        "Getting replica: %s, kind: %s, namespace: %s",
                        ownerRef.name,
                        ownerRef.kind,
                        namespace,
                    )

                    if replicas_dict.get(namespace + "/" + ownerRef.name):
                        rc = replicas_dict.get(namespace + "/" + ownerRef.name)
                        pod_replica_dict[namespace + "/" + ownerRef.name] = "DONE"
                        images = [image_sha(c.image) for c in pod.spec.containers]

                        # Since a commit will be built into a particular image and there could be multiple
                        # containers (images) per pod, we will push one metric per image/container in the
                        # pod template
                        for i in images:
                            if i is not None:
                                metric = DeployTimeMetric(
                                    name=rc.metadata.labels[pelorus.get_app_label()],
                                    namespace=namespace,
                                    labels=rc.metadata.labels,
                                    deploy_time=rc.metadata.creationTimestamp,
                                    image_sha=i,
                                )
                                metrics.append(metric)

    return metrics


def get_replicas(
    dyn_client: DynamicClient, apiVersion: str, objectName: str
) -> dict[str, object]:
    """Process Replicas for given Api Version and Object type (ReplicaSet or ReplicationController)"""
    replicas = {}
    try:
        apiResource = dyn_client.resources.get(api_version=apiVersion, kind=objectName)
        replicationobjects = apiResource.get(label_selector=pelorus.get_app_label())
        for replica in replicationobjects.items:
            replicas[replica.metadata.namespace + "/" + replica.metadata.name] = replica
    except ResourceNotFoundError:
        logging.debug(
            "API Object not found for version: %s object: %s", apiVersion, objectName
        )
        pass
    return replicas


if __name__ == "__main__":
    pelorus.load_kube_config()
    k8s_config = client.Configuration()
    k8s_client = client.api_client.ApiClient(configuration=k8s_config)
    dyn_client = DynamicClient(k8s_client)
    namespaces = None
    if os.environ.get("NAMESPACES") is not None:
        namespaces = [proj.strip() for proj in os.environ.get("NAMESPACES").split(",")]
    start_http_server(8080)
    REGISTRY.register(DeployTimeCollector(namespaces, dyn_client))
    while True:
        time.sleep(1)

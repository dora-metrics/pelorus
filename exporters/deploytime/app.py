import logging
import os
import re
import time
from typing import Iterable, Optional, Sequence

import attr
from kubernetes import client
from openshift.dynamic import DynamicClient
from openshift.dynamic.exceptions import ResourceNotFoundError
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY, GaugeMetricFamily

import pelorus

supported_replica_objects = {"ReplicaSet", "ReplicationController"}

# A NamespaceSpec lists namespaces to restrict the search to.
# Use None or an empty list to include all namespaces.
NamespaceSpec = Optional[Sequence[str]]


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
) -> Iterable[DeployTimeMetric]:
    visited_replicas = set()

    def already_seen(full_path: str) -> bool:
        return full_path in visited_replicas

    def mark_as_seen(full_path: str):
        visited_replicas.add(full_path)

    logging.info("generate_metrics: start")

    v1_pods = dyn_client.resources.get(api_version="v1", kind="Pod")
    if not namespaces:
        logging.info("No namespaces specified, watching all namespaces")
    else:
        logging.info("Watching namespaces %s", namespaces)

    def in_namespace(namespace: str) -> bool:
        return (not namespaces) or namespace in namespaces

    pods = v1_pods.get(
        label_selector=pelorus.get_app_label(), field_selector="status.phase=Running"
    ).items

    replicas_dict = (
        get_replicas(dyn_client, "v1", "ReplicationController")
        | get_replicas(dyn_client, "apps/v1", "ReplicaSet")
        | get_replicas(dyn_client, "extensions/v1beta1", "ReplicaSet")
    )

    for pod in pods:
        namespace = pod.metadata.namespace
        owner_refs = pod.metadata.ownerReferences
        if not in_namespace(namespace) or not owner_refs:
            continue

        logging.debug(
            "Getting Replicas for pod: %s in namespace: %s",
            pod.metadata.name,
            pod.metadata.namespace,
        )

        # Get deploytime from the owning controller of the pod.
        # We track all already-visited controllers to not duplicate metrics per-pod.
        for ref in owner_refs:
            full_path = f"{namespace}/{ref.name}"

            if ref.kind not in supported_replica_objects or already_seen(full_path):
                continue

            logging.debug(
                "Getting replica: %s, kind: %s, namespace: %s",
                ref.name,
                ref.kind,
                namespace,
            )

            if not (rc := replicas_dict.get(full_path)):
                continue

            mark_as_seen(full_path)
            images = (sha for c in pod.spec.containers if (sha := image_sha(c.image)))

            # Since a commit will be built into a particular image and there could be multiple
            # containers (images) per pod, we will push one metric per image/container in the
            # pod template
            for sha in images:
                metric = DeployTimeMetric(
                    name=rc.metadata.labels[pelorus.get_app_label()],
                    namespace=namespace,
                    labels=rc.metadata.labels,
                    deploy_time=rc.metadata.creationTimestamp,
                    image_sha=sha,
                )
                yield metric


def get_replicas(
    dyn_client: DynamicClient, apiVersion: str, objectName: str
) -> dict[str, object]:
    """Process Replicas for given Api Version and Object type (ReplicaSet or ReplicationController)"""
    try:
        apiResource = dyn_client.resources.get(api_version=apiVersion, kind=objectName)
        replicationobjects = apiResource.get(label_selector=pelorus.get_app_label())
        return {
            f"{replica.metadata.namespace}/{replica.metadata.name}": replica
            for replica in replicationobjects.items
        }
    except ResourceNotFoundError:
        logging.debug(
            "API Object not found for version: %s object: %s", apiVersion, objectName
        )
    return {}


if __name__ == "__main__":
    pelorus.load_kube_config()
    k8s_config = client.Configuration()
    k8s_client = client.api_client.ApiClient(configuration=k8s_config)
    dyn_client = DynamicClient(k8s_client)
    namespaces = [
        stripped
        for proj in os.environ.get("NAMESPACES", "").split(",")
        if (stripped := proj.strip())
    ]
    start_http_server(8080)
    REGISTRY.register(DeployTimeCollector(namespaces, dyn_client))
    while True:
        time.sleep(1)

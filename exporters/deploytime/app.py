from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Iterable, Optional

import attr
from kubernetes import client
from openshift.dynamic import DynamicClient
from openshift.dynamic.exceptions import ResourceNotFoundError
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY, GaugeMetricFamily

import pelorus

supported_replica_objects = {"ReplicaSet", "ReplicationController"}


class DeployTimeCollector:
    _warned_missing_replicas: set[str]
    """Replicas with missing app labels that we've already warned about"""

    def __init__(self, namespaces: set[str], client: DynamicClient, prod_label: str):
        self._namespaces = namespaces
        self.client = client
        self.prod_label = prod_label
        self._warned_missing_replicas = set()
        self.app_label = pelorus.get_app_label()

    def collect(self) -> Iterable[GaugeMetricFamily]:
        logging.info("collect: start")
        metric = GaugeMetricFamily(
            "deploy_timestamp",
            "Deployment timestamp",
            labels=["namespace", "app", "image_sha"],
        )

        namespaces = self.get_and_log_namespaces()
        if not namespaces:
            return []

        metrics = self.generate_metrics(namespaces)
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

    def get_and_log_namespaces(self) -> set[str]:
        """
        Get the set of namespaces to watch, and log what they are.
        They will be either:
        1. The namespaces explicitly specified
        2. The namespaces matched by PROD_LABEL
        3. If neither namespaces nor the PROD_LABEL is given, then implicitly matches all namespaces.
        """
        if self._namespaces:
            logging.info("Watching namespaces %s", self._namespaces)
            return self._namespaces

        if self.prod_label:
            logging.info(
                "No namespaces specified, watching all namespaces with given PROD_LABEL (%s)",
                self.prod_label,
            )
            query_args = dict(label_selector=prod_label)
        else:
            logging.info(
                "No namespaces specified and no PROD_LABEL given, watching all namespaces."
            )
            query_args = dict()

        all_namespaces = self.client.resources.get(api_version="v1", kind="Namespace")
        namespaces = {
            namespace.metadata.name
            for namespace in all_namespaces.get(**query_args).items
        }
        logging.info("Watching namespaces %s", namespaces)
        if not namespaces:
            logging.warning(
                "No NAMESPACES given and PROD_LABEL did not return any matching namespaces."
            )
        return namespaces

    def _get_rc_app_label_or_warn(self, rc) -> Optional[str]:
        """
        Get the application label from the given replicator,
        or log a warning once if it's not present.
        """
        if name := rc.metadata.labels[self.app_label]:
            return name

        full_path = f"{rc.metadata.namespace}/{rc.metadata.name}"
        if full_path not in self._warned_missing_replicas:
            logging.warn(
                f"{rc.kind} {full_path} is missing app label {self.app_label}, skipping."
            )
            self._warned_missing_replicas.add(full_path)

        return None

    def generate_metrics(
        self,
        namespaces: set[str],
    ) -> Iterable[DeployTimeMetric]:
        visited_replicas = set()

        def already_seen(full_path: str) -> bool:
            return full_path in visited_replicas

        def mark_as_seen(full_path: str):
            visited_replicas.add(full_path)

        logging.info("generate_metrics: start")

        # get all running Pods with the app label
        v1_pods = self.client.resources.get(api_version="v1", kind="Pod")
        pods = v1_pods.get(
            label_selector=self.app_label,
            field_selector="status.phase=Running",
        ).items

        replicas_dict = (
            get_replicas(self.client, "v1", "ReplicationController")
            | get_replicas(self.client, "apps/v1", "ReplicaSet")
            | get_replicas(self.client, "extensions/v1beta1", "ReplicaSet")
        )

        pods = (
            pod
            for pod in pods
            if pod.metadata.namespace in namespaces and pod.metadata.ownerReferences
        )
        pods_and_owners = (
            (pod, owner_ref)
            for pod in pods
            for owner_ref in pod.metadata.ownerReferences
        )

        for pod, owner_ref in pods_and_owners:
            namespace = pod.metadata.namespace

            # Get deploytime from the owning controller of the pod.
            # We track all already-visited controllers to not duplicate metrics per-pod.
            full_path = f"{namespace}/{owner_ref.name}"

            if owner_ref.kind not in supported_replica_objects or already_seen(
                full_path
            ):
                continue

            logging.debug(
                "Examining replica %s of kind %s for pod %s in namespace: %s",
                owner_ref.name,
                owner_ref.kind,
                pod.metadata.name,
                namespace,
            )

            if not (rc := replicas_dict.get(full_path)):
                continue

            mark_as_seen(full_path)

            if not (name := self._get_rc_app_label_or_warn(rc)):
                continue

            container_shas = (
                image_sha(container.image) for container in pod.spec.containers
            )
            container_status_shas = (
                image_sha(status.imageID) for status in pod.status.containerStatuses
            )
            images = {sha for sha in container_shas if sha} | {
                sha for sha in container_status_shas if sha
            }

            # Since a commit will be built into a particular image and there could be multiple
            # containers (images) per pod, we will push one metric per image/container in the
            # pod template
            for sha in images:
                metric = DeployTimeMetric(
                    name=name,
                    namespace=namespace,
                    labels=rc.metadata.labels,
                    deploy_time=rc.metadata.creationTimestamp,
                    image_sha=sha,
                )
                yield metric


@attr.frozen(kw_only=True)
class DeployTimeMetric:
    name: str
    namespace: str
    # WARNING: do not mutate the dict after hashing or things may break.
    labels: dict[str, str]
    deploy_time: object
    image_sha: str

    def __hash__(self):
        return hash(
            (
                self.name,
                self.namespace,
                hash(tuple(self.labels.items())),
                self.deploy_time,
                self.image_sha,
            )
        )


def image_sha(image_url_or_id: str) -> Optional[str]:
    """
    Gets the hash of the image, extracted from the image URL or image ID.

    Specifically, everything after the first `sha256:` seen.
    """
    sha_regex = re.compile(r"sha256:.*")
    if match := sha_regex.search(image_url_or_id):
        return match.group()
    else:
        # This may be noisy if there are a lot of pods where the container
        # spec doesn't have a SHA but the status does.
        # But since it's only in debug logs, it doesn't matter.
        logging.debug("Skipping unresolved image reference: %s", image_url_or_id)
        return None


def get_replicas(
    dyn_client: DynamicClient, apiVersion: str, objectName: str
) -> dict[str, Any]:
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
    namespaces = {
        stripped
        for proj in os.environ.get("NAMESPACES", "").split(",")
        if (stripped := proj.strip())
    }
    prod_label = pelorus.get_prod_label()
    if namespaces and prod_label:
        logging.warning("If NAMESPACES are given, PROD_LABEL is ignored.")
    elif not (namespaces or prod_label):
        logging.info("No NAMESPACES or PROD_LABEL given, will watch all namespaces")
    start_http_server(8080)
    REGISTRY.register(DeployTimeCollector(namespaces, dyn_client, prod_label))
    while True:
        time.sleep(1)

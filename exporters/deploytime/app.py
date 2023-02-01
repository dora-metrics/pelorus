import logging
import re
import time
from typing import Iterable, Optional

from attrs import field, frozen
from openshift.dynamic import DynamicClient, ResourceInstance
from openshift.dynamic.exceptions import ResourceNotFoundError
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY, GaugeMetricFamily

import pelorus
from deploytime import DeployTimeMetric
from pelorus.config import load_and_log, no_env_vars
from pelorus.config.converters import comma_separated

supported_replica_objects = {"ReplicaSet", "ReplicationController"}


@frozen
class DeployTimeCollector(pelorus.AbstractPelorusExporter):
    client: DynamicClient = field(metadata=no_env_vars())
    namespaces: set[str] = field(factory=set, converter=comma_separated(set))
    prod_label: str = field(default=pelorus.DEFAULT_PROD_LABEL)

    def __attrs_post_init__(self):
        if self.namespaces and (self.prod_label != pelorus.DEFAULT_PROD_LABEL):
            logging.warning("If NAMESPACES are given, PROD_LABEL is ignored.")

    def collect(self) -> Iterable[GaugeMetricFamily]:
        logging.info("collect: start")

        metrics = self.generate_metrics()

        deploy_timestamp_metric = GaugeMetricFamily(
            "deploy_timestamp",
            "Deployment timestamp",
            labels=["namespace", "app", "image_sha"],
        )
        deployment_active_metric = GaugeMetricFamily(
            "deployment_active",
            "Active deployments in cluster",
            labels=["namespace", "app", "image_sha"],
        )

        for m in metrics:
            logging.info(
                "Collected deploy_timestamp{namespace=%s, app=%s, image=%s} %s (%s)",
                m.namespace,
                m.name,
                m.image_sha,
                m.deploy_time_timestamp,
                m.deploy_time,
            )
            deploy_timestamp_metric.add_metric(
                [m.namespace, m.name, m.image_sha],
                m.deploy_time_timestamp,
                timestamp=m.deploy_time_timestamp,
            )
            logging.info(
                "Collected deployment_active{namespace=%s, app=%s, image=%s} %s (%s)",
                m.namespace,
                m.name,
                m.image_sha,
                m.deploy_time_timestamp,
                m.deploy_time,
            )
            deployment_active_metric.add_metric(
                [m.namespace, m.name, m.image_sha],
                m.deploy_time_timestamp,
            )
        return (deploy_timestamp_metric, deployment_active_metric)

    def get_and_log_namespaces(self) -> set[str]:
        """
        Get the set of namespaces to watch, and log what they are.
        They will be either:
        1. The namespaces explicitly specified
        2. The namespaces matched by PROD_LABEL
        3. If neither namespaces nor the PROD_LABEL is given, then implicitly matches all namespaces.
        """
        if self.namespaces:
            logging.info("Watching namespaces %s", self.namespaces)
            return self.namespaces

        if self.prod_label:
            logging.info(
                "No namespaces specified, watching all namespaces with given PROD_LABEL (%s)",
                self.prod_label,
            )
            query_args = dict(label_selector=self.prod_label)
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

    def generate_metrics(self) -> Iterable[DeployTimeMetric]:
        namespaces = self.get_and_log_namespaces()
        if not namespaces:
            return []

        app_label = self.app_label
        visited_replicas = set()

        def already_seen(full_path: str) -> bool:
            return full_path in visited_replicas

        def mark_as_seen(full_path: str):
            visited_replicas.add(full_path)

        logging.info("generate_metrics: start")

        # get all running Pods with the app label
        v1_pods = self.client.resources.get(api_version="v1", kind="Pod")
        pods = v1_pods.get(
            label_selector=app_label, field_selector="status.phase=Running"
        ).items

        replicas_dict = (
            self.get_replicas("v1", "ReplicationController")
            | self.get_replicas("apps/v1", "ReplicaSet")
            | self.get_replicas("extensions/v1beta1", "ReplicaSet")
        )

        for pod in pods:
            namespace = pod.metadata.namespace
            owner_refs = pod.metadata.ownerReferences
            if namespace not in namespaces or not owner_refs:
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
                        name=rc.metadata.labels[app_label],
                        namespace=namespace,
                        labels=rc.metadata.labels,
                        deploy_time=rc.metadata.creationTimestamp,
                        image_sha=sha,
                    )
                    yield metric

    def get_replicas(
        self, apiVersion: str, objectName: str
    ) -> dict[str, ResourceInstance]:
        """Process Replicas for given Api Version and Object type (ReplicaSet or ReplicationController)"""
        try:
            apiResource = self.client.resources.get(
                api_version=apiVersion, kind=objectName
            )
            replicationobjects = apiResource.get(label_selector=self.app_label)
            return {
                f"{replica.metadata.namespace}/{replica.metadata.name}": replica
                for replica in replicationobjects.items
            }
        except ResourceNotFoundError:
            logging.debug(
                "API Object not found for version: %s object: %s",
                apiVersion,
                objectName,
            )
        return {}


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


if __name__ == "__main__":
    pelorus.setup_logging()
    dyn_client = pelorus.utils.get_k8s_client()

    collector = load_and_log(DeployTimeCollector, other=dict(client=dyn_client))

    REGISTRY.register(collector)
    start_http_server(8080)
    while True:
        time.sleep(1)

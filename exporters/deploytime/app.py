import logging
import time
from typing import Iterable

from attrs import field, frozen
from openshift.dynamic import DynamicClient
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY, GaugeMetricFamily

import pelorus
from deploytime import DeployTimeMetric
from pelorus.config import load_and_log, no_env_vars
from pelorus.config.converters import comma_separated
from pelorus.timeutil import METRIC_TIMESTAMP_THRESHOLD_MINUTES, is_out_of_date
from provider_common.openshift import (
    filter_pods_by_replica_uid,
    get_and_log_namespaces,
    get_images_from_pod,
    get_owner_object_from_child,
    get_running_pods,
)


@frozen
class DeployTimeCollector(pelorus.AbstractPelorusExporter):
    client: DynamicClient = field(metadata=no_env_vars())
    namespaces: set[str] = field(factory=set, converter=comma_separated(set))
    prod_label: str = field(default=pelorus.DEFAULT_PROD_LABEL)

    def __attrs_post_init__(self):
        if self.namespaces and (self.prod_label != pelorus.DEFAULT_PROD_LABEL):
            logging.warning("If NAMESPACES are given, PROD_LABEL is ignored.")

    def collect(self) -> Iterable[GaugeMetricFamily]:
        logging.debug("collect: start")
        metrics = self.generate_metrics()

        deploy_timestamp_metric = GaugeMetricFamily(
            "deploy_timestamp",
            "Deployment timestamp",
            labels=["namespace", "app", "image_sha"],
        )

        number_of_dropped = 0

        for m in metrics:
            if not is_out_of_date(str(m.deploy_time_timestamp)):
                logging.debug(
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
            else:
                number_of_dropped += 1
                logging.debug(
                    "Deployment too old to be collected: deploy_timestamp{namespace=%s, app=%s, image=%s} %s (%s)",
                    m.namespace,
                    m.name,
                    m.image_sha,
                    m.deploy_time_timestamp,
                    m.deploy_time_timestamp,
                )
        if number_of_dropped:
            logging.debug(
                "Number of deployments that are older then %smin and won't be collected: %s",
                METRIC_TIMESTAMP_THRESHOLD_MINUTES,
                number_of_dropped,
            )
        yield deploy_timestamp_metric

    def generate_metrics(self) -> Iterable[DeployTimeMetric]:
        namespaces = get_and_log_namespaces(
            self.client, self.namespaces, self.prod_label
        )

        if not namespaces:
            return []

        logging.debug("generate_metrics: start")

        pods = get_running_pods(self.client, namespaces, self.app_label)

        # Build dictionary with controllers and retrieved pods
        replica_pods_dict = filter_pods_by_replica_uid(pods)

        for uid, pod in replica_pods_dict.items():
            replicas = get_owner_object_from_child(self.client, uid, pod)

            # Since a commit will be built into a particular image and there could be multiple
            # containers (images) per pod, we will push one metric per image/container in the
            # pod template
            images = get_images_from_pod(pod)

            for sha in images.keys():
                metric = DeployTimeMetric(
                    name=pod.metadata.labels[self.app_label],
                    namespace=pod.metadata.namespace,
                    labels=pod.metadata.labels,
                    deploy_time=replicas.get(uid).metadata.creationTimestamp,
                    image_sha=sha,
                )
                yield metric


if __name__ == "__main__":
    pelorus.setup_logging()
    dyn_client = pelorus.utils.get_k8s_client()

    collector = load_and_log(DeployTimeCollector, other=dict(client=dyn_client))

    REGISTRY.register(collector)
    start_http_server(8080)
    while True:
        time.sleep(1)

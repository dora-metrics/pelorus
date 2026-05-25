import logging
import time
from typing import Iterable

from attrs import field, frozen
from kubernetes.dynamic import DynamicClient
from prometheus_client import Counter, Gauge, start_http_server
from prometheus_client.core import REGISTRY, GaugeMetricFamily

import pelorus
from deploytime import DeployTimeMetric
from pelorus.config import load_and_log, no_env_vars
from pelorus.config.converters import comma_separated
from pelorus.timeutil import METRIC_TIMESTAMP_THRESHOLD_MINUTES, is_out_of_date_timestamp
from provider_common import format_app_name
from provider_common.openshift import (
    filter_pods_by_replica_uid,
    get_and_log_namespaces,
    get_images_from_pod,
    get_owner_object_from_child,
    get_running_pods,
)


_collection_duration = Gauge(
    "pelorus_deploytime_collection_duration_seconds",
    "Duration of the last deploytime metric collection in seconds",
)
_collection_errors = Counter(
    "pelorus_deploytime_collection_errors_total",
    "Total number of deploytime metric collection errors",
)
_last_collection_count = Gauge(
    "pelorus_deploytime_last_collection_count",
    "Number of metrics returned by the last deploytime collection",
)
_pod_failures = Counter(
    "pelorus_deploytime_pod_failures_total",
    "Total number of individual pod metric collection failures",
)


@frozen
class DeployTimeCollector(pelorus.AbstractPelorusExporter):
    client: DynamicClient = field(metadata=no_env_vars())
    namespaces: set[str] = field(factory=set, converter=comma_separated(set))
    prod_label: str = field(default=pelorus.DEFAULT_PROD_LABEL)

    _DEPLOY_METRIC_NAME = "deploy_timestamp"
    _DEPLOY_METRIC_HELP = "Deployment timestamp"
    _DEPLOY_METRIC_LABELS = ["namespace", "app", "image_sha"]

    def __attrs_post_init__(self):
        if self.namespaces and (self.prod_label != pelorus.DEFAULT_PROD_LABEL):
            logging.warning("If NAMESPACES are given, PROD_LABEL is ignored.")

    @staticmethod
    def _new_deploy_metric():
        return GaugeMetricFamily(
            DeployTimeCollector._DEPLOY_METRIC_NAME,
            DeployTimeCollector._DEPLOY_METRIC_HELP,
            labels=DeployTimeCollector._DEPLOY_METRIC_LABELS,
        )

    def describe(self) -> list[GaugeMetricFamily]:
        return [self._new_deploy_metric()]

    def collect(self) -> Iterable[GaugeMetricFamily]:
        logging.debug("collect: start")
        start = time.monotonic()
        collected_count = 0
        try:
            metrics = self.generate_metrics()

            deploy_timestamp_metric = self._new_deploy_metric()

            number_of_dropped = 0

            for m in metrics:
                if not is_out_of_date_timestamp(m.deploy_time_timestamp):
                    logging.debug(
                        "Collected deploy_timestamp{namespace=%s, app=%s, image=%s} %s (%s)",
                        m.namespace,
                        m.name,
                        m.image_sha,
                        m.deploy_time_timestamp,
                        m.deploy_time,
                    )
                    deploy_timestamp_metric.add_metric(
                        [m.namespace, format_app_name(m.name), m.image_sha],
                        m.deploy_time_timestamp,
                        timestamp=m.deploy_time_timestamp,
                    )
                    collected_count += 1
                else:
                    number_of_dropped += 1
                    logging.debug(
                        "Deployment too old to be collected: deploy_timestamp{namespace=%s, app=%s, image=%s} %s (%s)",
                        m.namespace,
                        m.name,
                        m.image_sha,
                        m.deploy_time_timestamp,
                        m.deploy_time,
                    )
            if number_of_dropped:
                logging.info(
                    "Dropped %d deployments older than %dmin",
                    number_of_dropped,
                    METRIC_TIMESTAMP_THRESHOLD_MINUTES,
                )
            yield deploy_timestamp_metric
        except Exception:
            _collection_errors.inc()
            logging.error("Deploy time metric collection failed", exc_info=True)
            yield self._new_deploy_metric()
        finally:
            duration = time.monotonic() - start
            _collection_duration.set(duration)
            _last_collection_count.set(collected_count)
            logging.info("collect: %d metrics in %.2fs", collected_count, duration)

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
            try:
                replicas = get_owner_object_from_child(self.client, uid, pod)

                replica = replicas.get(uid)
                if replica is None:
                    logging.debug(
                        "Parent object not found for pod %s (uid=%s), skipping",
                        pod.metadata.name, uid,
                    )
                    continue

                # Multiple containers (images) per pod: emit one metric per image
                images = get_images_from_pod(pod)

                for sha in images:
                    metric = DeployTimeMetric(
                        name=pod.metadata.labels[self.app_label],
                        namespace=pod.metadata.namespace,
                        labels=pod.metadata.labels,
                        deploy_time=replica.metadata.creationTimestamp,
                        image_sha=sha,
                    )
                    yield metric
            except Exception:
                _pod_failures.inc()
                logging.error(
                    "Failed to process pod %s/%s, skipping",
                    getattr(getattr(pod, "metadata", None), "namespace", "?"),
                    getattr(getattr(pod, "metadata", None), "name", "?"),
                    exc_info=True,
                )


def set_up(prod: bool = True) -> DeployTimeCollector:
    pelorus.setup_logging(prod=prod)
    dyn_client = pelorus.utils.get_k8s_client()

    collector = load_and_log(DeployTimeCollector, other=dict(client=dyn_client))

    REGISTRY.register(collector)
    return collector


if __name__ == "__main__":
    try:
        set_up()
    except Exception as e:
        logging.error(
            "Failed to configure deploytime exporter: %s. "
            "Check NAMESPACES and PROD_LABEL settings. "
            "Starting metrics server anyway - configure and restart to collect deploy data.",
            e,
            exc_info=True,
        )

    start_http_server(pelorus.EXPORTER_PORT)
    logging.info("Deploytime exporter ready, serving metrics on :%d", pelorus.EXPORTER_PORT)
    while True:
        time.sleep(1)

#!/usr/bin/env python3
#
# Copyright Red Hat
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

import json
import logging
import queue
import shlex
import subprocess
import threading
import time
from collections import OrderedDict
from typing import Iterable, Optional

from attrs import define
from kubernetes.dynamic.resource import ResourceField
from prometheus_client import Counter

from committime import CommitMetric
from committime.collector_base import AbstractCommitCollector, _build_failures
from pelorus.timeutil import parse_commit_timestamp
from provider_common.openshift import (
    filter_pods_by_replica_uid,
    get_and_log_namespaces,
    get_images_from_pod,
    get_running_pods,
)

_skopeo_worker_errors = Counter(
    "pelorus_committime_skopeo_errors_total",
    "Total number of errors in the skopeo background worker",
)

# A queue to store image URI values to be processed.
# Bounded to prevent unbounded memory growth when the skopeo worker
# can't keep pace with new image discoveries.
image_shas_uris_queue = queue.Queue(maxsize=1000)
# Cache threshold in seconds for the in-memory image label cache.
# Cached entries expire when the threshold is exceeded and the image SHA
# is no longer in use by any running Pod. This avoids excessive skopeo calls
# while still allowing pods to be temporarily not running before expiring its metric.
CACHE_THRESHOLD_1_DAY = 60 * 60 * 24

# We store skopeo failures and we re-try maximum SKOPEO_MAX_RETRY times per
# one image URI. This is to prevent too many calls to the external container
# registries. We have a timeout here, so after some time the failed image URI
# will be retried anyway. If the pod is not Running anymore the cache expires
# right away.
skopeo_failures_lock = threading.RLock()
# The dictionary where the key is an uuid and the value a Tuple
# where we store number of retries and the time of last check.
# OrderedDict enables O(1) eviction of the oldest entry when at capacity.
skopeo_failures: OrderedDict[str, tuple[int, float]] = OrderedDict()
SKOPEO_MAX_RETRY = 3
CACHE_SKOPEO_FAILURE_THRESHOLD_2_DAYS = 60 * 60 * 24 * 2
_SKOPEO_FAILURES_MAX = 5_000

image_label_cache_lock = threading.Lock()
image_label_cache: OrderedDict[str, tuple[dict, float]] = OrderedDict()
_IMAGE_LABEL_CACHE_MAX = 10_000


# The directory where ca.crt is mounted
CA_CRT_DIR = "/var/run/secrets/kubernetes.io/serviceaccount/"


class SkopeoDataException(Exception):
    "An error that occurred during a Skopeo call"


def _cache_container_images_labels(sha_256: str, labels: dict) -> None:
    with image_label_cache_lock:
        if sha_256 not in image_label_cache:
            if len(image_label_cache) >= _IMAGE_LABEL_CACHE_MAX:
                image_label_cache.popitem(last=False)
            logging.debug("Adding SHA256 to the cache: %s", sha_256)
            image_label_cache[sha_256] = (labels, time.time())


def _cleanup_cache(active_shas: set) -> None:
    with image_label_cache_lock:
        current_time = time.time()

        expired_shas = [
            sha
            for sha, (_, insertion_time) in image_label_cache.items()
            if current_time - insertion_time > CACHE_THRESHOLD_1_DAY
            and sha not in active_shas
        ]
        for sha_256 in expired_shas:
            image_label_cache.pop(sha_256, None)


def _add_skopeo_failure(sha_256: str) -> None:
    with skopeo_failures_lock:
        logging.debug("Adding SHA256 to the failures: %s", sha_256)
        if sha_256 not in skopeo_failures:
            if len(skopeo_failures) >= _SKOPEO_FAILURES_MAX:
                skopeo_failures.popitem(last=False)
            skopeo_failures[sha_256] = (1, time.time())
        else:
            skopeo_failures[sha_256] = (skopeo_failures[sha_256][0] + 1, time.time())
            skopeo_failures.move_to_end(sha_256)


def _remove_from_skopeo_failure(sha_256: str) -> None:
    with skopeo_failures_lock:
        if skopeo_failures.pop(sha_256, None) is not None:
            logging.debug("Removing SHA256 from the failures: %s", sha_256)


def _sha256_valid_to_be_checked(sha_256: str) -> bool:
    """
    Checks if the sha256 of an image was previously in
    failures. If it was then it checks if the number of retries
    was above threshold.

    If it was then we check if the time threshold was met.
    """
    with skopeo_failures_lock:
        if sha_256 not in skopeo_failures:
            return True

        no_failures, timestamp = skopeo_failures[sha_256]
        if no_failures < SKOPEO_MAX_RETRY:
            return True

        if time.time() - timestamp > CACHE_SKOPEO_FAILURE_THRESHOLD_2_DAYS:
            skopeo_failures.pop(sha_256, None)
            return True

    return False


def get_labels_from_image(sha_256: str, image_uri: str) -> dict[str, str]:
    # Check if the sha_256 is in the failures
    # and if we should continue based on the SKOPEO_MAX_RETRY
    # or CACHE_SKOPEO_FAILURE_THRESHOLD_2_DAYS
    if not _sha256_valid_to_be_checked(sha_256):
        logging.debug("Skipping skopeo for: %s", sha_256)
        raise SkopeoDataException("Sha not to be checked")

    logging.debug("Running skopeo for: %s", sha_256)
    command = ["skopeo", "inspect", "--cert-dir", CA_CRT_DIR, image_uri]
    logging.debug("Running command: %s", shlex.join(command))
    process = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        output, stderr = process.communicate(timeout=120)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.communicate()
        _add_skopeo_failure(sha_256)
        raise SkopeoDataException("skopeo timed out after 120s") from exc
    output = output.decode("utf-8", errors="replace").strip()
    if process.returncode != 0:
        _add_skopeo_failure(sha_256)
        stderr = stderr.decode("utf-8", errors="replace").strip()
        logging.warning("Error from skopeo for %s: %s", command, stderr)
        raise SkopeoDataException(stderr)

    try:
        image_data = json.loads(output)
        labels = image_data.get("Labels", {})
    except json.JSONDecodeError as e:
        _add_skopeo_failure(sha_256)
        logging.warning("Error from decoding JSON for %s: %s", sha_256, e.msg)
        raise SkopeoDataException("Error: Invalid JSON output") from e

    # We got the labels, so remove them from the potential
    # existence in the failures.
    _remove_from_skopeo_failure(sha_256)
    logging.debug("Found the following labels for image %s: %s", image_uri, labels)
    return labels


def _skopeo_worker() -> None:
    loop_count = 1
    while True:
        logging.debug("Worker loop: %s", loop_count)
        loop_count += 1
        sha_pop = image_shas_uris_queue.get()
        try:
            for sha_256, sha_uri in sha_pop.items():
                labels = get_labels_from_image(sha_256, sha_uri)
                _cache_container_images_labels(sha_256, labels)
        except SkopeoDataException:
            _skopeo_worker_errors.inc()
            logging.debug("Skopeo worker: expected failure for image %s", sha_pop, exc_info=True)
        except Exception:
            _skopeo_worker_errors.inc()
            logging.warning(
                "Skopeo worker failed to process image labels for %s",
                sha_pop,
                exc_info=True,
            )

        image_shas_uris_queue.task_done()


# Start the daemon thread which checks for the queue and gathers
# labels for the queued items.
skopeo_cache_thread = threading.Thread(target=_skopeo_worker, daemon=True)
skopeo_cache_thread.start()


def _add_image_to_get_label_queue(sha_256: str, image_uri: str) -> None:
    """
    Function that puts the sha and corresponding image uri to the queue
    to be processed by our skopeo worker Thread.
    """

    with image_label_cache_lock:
        if sha_256 in image_label_cache:
            return
    logging.debug("Adding SHA256 to the SKOPEO queue: %s", sha_256)
    try:
        image_shas_uris_queue.put_nowait({sha_256: image_uri})
    except queue.Full:
        logging.warning("Skopeo queue full, dropping image %s", sha_256)


def _set_commit_metadata(
    pod: ResourceField,
    date_label: str,
    hash_label: str,
    repo_url_label: str,
    sha_256: str,
    date_format: Optional[str] = None,
) -> None:
    with image_label_cache_lock:
        entry = image_label_cache.get(sha_256, None)

    logging.debug("Got image labels for: %s", sha_256)
    if entry and isinstance(entry, tuple) and isinstance(entry[0], dict):
        labels = entry[0]
        pod.metadata.commit_hash = labels.get(hash_label)
        commit_time = labels.get(date_label)
        if commit_time:
            try:
                pod.metadata.commit_timestamp = parse_commit_timestamp(
                    commit_time, date_format
                )
            except (ValueError, AttributeError):
                logging.warning(
                    "Can't parse commit timestamp for sha %s, raw value: %s",
                    sha_256, commit_time,
                    exc_info=True,
                )
        repo_url = labels.get(repo_url_label)
        if not repo_url:
            repo_url = "unknown"
        pod.metadata.repo_url = repo_url


@define(kw_only=True)
class ContainerImageCommitCollector(AbstractCommitCollector):
    date_format: str

    date_annotation_name: str = CommitMetric._ANNOTATION_MAPPING["commit_time"]
    hash_annotation_name: str = CommitMetric._ANNOTATION_MAPPING["commit_hash"]
    repo_url_annotation_name: str = CommitMetric._ANNOTATION_MAPPING["repo_url"]

    def get_commit_time(self, metric) -> Optional[CommitMetric]:
        # Not used — this collector overrides generate_metrics() entirely.
        # Exists only to satisfy the abstract base class contract.
        return None

    # overrides collector_base.generate_metrics()
    def generate_metrics(self) -> Iterable[CommitMetric]:
        namespaces = get_and_log_namespaces(
            self.kube_client, self.namespaces, self.prod_label
        )

        if not namespaces:
            return

        logging.debug("generate_metrics: start")

        active_shas = set()

        pods = get_running_pods(self.kube_client, namespaces, self.app_label)

        # Build dictionary with controllers and retrieved pods
        replica_pods_dict = filter_pods_by_replica_uid(pods)

        for pod in replica_pods_dict.values():
            try:
                # Since a commit will be built into a particular image and there could be multiple
                # containers (images) per pod, we will push one metric per image/container in the
                # pod template
                images = get_images_from_pod(pod)

                for sha, image_uri in images.items():
                    active_shas.add(sha)
                    _add_image_to_get_label_queue(sha, image_uri)
                    _set_commit_metadata(
                        pod,
                        self.date_annotation_name,
                        self.hash_annotation_name,
                        self.repo_url_annotation_name,
                        sha,
                        self.date_format,
                    )
                    if pod.metadata.commit_timestamp and pod.metadata.commit_hash:
                        app_name = pod.metadata.labels.get(self.app_label)
                        if not app_name:
                            logging.warning(
                                "Pod %s/%s missing app label %s, skipping",
                                pod.metadata.namespace, pod.metadata.name, self.app_label,
                            )
                            continue
                        metric = CommitMetric(
                            name=app_name,
                            namespace=pod.metadata.namespace,
                            labels=pod.metadata.labels,
                            commit_hash=pod.metadata.commit_hash,
                            commit_timestamp=pod.metadata.commit_timestamp,
                            image_hash=sha,
                        )
                        metric.commit_link = pod.metadata.repo_url
                        yield metric
            except Exception:
                _build_failures.inc()
                logging.error(
                    "Failed to process pod %s/%s, skipping",
                    getattr(getattr(pod, "metadata", None), "namespace", "?"),
                    getattr(getattr(pod, "metadata", None), "name", "?"),
                    exc_info=True,
                )

        _cleanup_cache(active_shas)

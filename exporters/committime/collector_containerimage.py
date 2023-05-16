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
import subprocess
import threading
import time
from typing import Dict, Iterable, Optional, Tuple

from attr import define
from openshift.dynamic.resource import ResourceField

from committime import CommitMetric
from committime.collector_base import AbstractCommitCollector
from pelorus.timeutil import parse_guessing_timezone_DYNAMIC, to_epoch_from_string
from provider_common.openshift import (
    filter_pods_by_replica_uid,
    get_and_log_namespaces,
    get_images_from_pod,
    get_running_pods,
)

skopeo_lock = threading.Lock()

# A queue to store image URI values to be processed
image_shas_uris_queue = queue.Queue()
# Use to track if the image is already in the queue
sha_in_queue = set()

# Cache threshold in seconds, used by our in memory cache or storing image labels.
# The cache may expire only when the image is not in use by running Pod anymore,
# so we don't waste the skopeo calls to the external registries, but we still allow
# pods to be not running for a while before we expire it's metric.
CACHE_THRESHOLD_1_DAYS = 60 * 60 * 24

# We store skopeo failures and we re-try maximum SKOPEO_MAX_RETRY times per
# one image URI. This is to prevent too many calls to the external container
# registries. We have a timeout here, so after some time the failed image URI
# will be retried anyway. If the pod is not Running anymore the cache expires
# right away.
skopeo_failures_lock = threading.Lock()
# The dictionary where the key is an uuid and the value a Tuple
# where we store number of retries and the time of last check
skopeo_failures: Dict[str, Tuple[int, float]] = {}
SKOPEO_MAX_RETRY = 3
CACHE_SKOPEO_FAILURE_THRESHOLD_2_DAYS = 60 * 60 * 24 * 2

image_label_cache_lock = threading.Lock()
image_label_cache: Dict[str, Tuple[Dict, float]] = {}

# Store pods that are running, needed for cleanup
running_pods_shas_lock = threading.Lock()
running_pods_shas = set()


class SkopeoDataException(Exception):
    "An error that occurred Skopeo call"
    pass


def _add_to_cleanup_set(sha_256: str) -> None:
    with running_pods_shas_lock:
        running_pods_shas.add(sha_256)


def _clear_cleanup_set() -> None:
    with running_pods_shas_lock:
        running_pods_shas.clear()


def _cache_container_images_labels(sha_256: str, labels: Dict) -> None:
    with image_label_cache_lock:
        if sha_256 not in image_label_cache:
            logging.debug(f"Adding SHA256 to the cache: {sha_256} ")
            image_label_cache[sha_256] = (labels, time.time())


def _cleanup_cache() -> None:
    with running_pods_shas_lock, image_label_cache_lock:
        current_time = time.time()

        expired_shas = [
            sha
            for sha, (_, insertion_time) in image_label_cache.items()
            if current_time - insertion_time > CACHE_THRESHOLD_1_DAYS
            and sha not in running_pods_shas
        ]
        for sha_256 in expired_shas:
            image_label_cache.pop(sha_256, None)


def _add_skopeo_failure(sha_256: str) -> None:
    with skopeo_failures_lock:
        logging.debug(f"Adding SHA256 to the failures: {sha_256} ")
        if sha_256 not in skopeo_failures:
            skopeo_failures[sha_256] = (1, time.time())
        else:
            skopeo_failures[sha_256] = (skopeo_failures[sha_256][0] + 1, time.time())


def _remove_from_skopeo_failure(sha_256: str) -> None:
    with skopeo_failures_lock:
        if sha_256 in skopeo_failures:
            logging.debug(f"Removing SHA256 from the failures: {sha_256} ")
            skopeo_failures.pop(sha_256, None)


def _sha256_valid_to_be_checked(sha_256: str) -> bool:
    """
    Checks if the sha256 of an image was previously in
    failures. If it was then it checks if the number of retries
    was above threashold.

    If it was then we check if the time treshold was met.
    """
    with skopeo_failures_lock:
        if sha_256 not in skopeo_failures:
            return True

        no_failures, timestamp = skopeo_failures[sha_256]
        if no_failures < SKOPEO_MAX_RETRY:
            return True

    # Must be outside of the failures lock, otherwise we will
    # deadlock with the _remove_from_skopeo_failure() call
    if time.time() - timestamp > CACHE_SKOPEO_FAILURE_THRESHOLD_2_DAYS:
        _remove_from_skopeo_failure(sha_256)
        return True

    return False


def get_labels_from_image(sha_256: str, image_uri: str) -> Dict[str, str]:
    # Check if the sha_256 is in the failures
    # and if we should continue based on the SKOPEO_MAX_RETRY
    # or CACHE_SKOPEO_FAILURE_THRESHOLD_2_DAYS
    if not _sha256_valid_to_be_checked(sha_256):
        logging.debug(f"Skipping skopeo for: {sha_256}")
        raise SkopeoDataException("Sha not to be checked")

    logging.debug(f"Running skopeo for: {sha_256}")
    command = f"skopeo inspect {image_uri}"
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )
    output, stderr = process.communicate()
    output = output.decode("utf-8").strip()
    if process.returncode != 0:
        _add_skopeo_failure(sha_256)
        raise SkopeoDataException(stderr.decode().strip())

    try:
        image_data = json.loads(output)
        labels = image_data.get("Labels", {})
    except json.JSONDecodeError:
        _add_skopeo_failure(sha_256)
        raise SkopeoDataException("Error: Invalid JSON output")

    # We got the labels, so remove them from the potential
    # existence in the failures.
    _remove_from_skopeo_failure(sha_256)
    return labels


def _skopeo_worker() -> None:
    loop_count = 1
    while True:
        logging.debug(f"Worker loop: {loop_count}")
        loop_count += 1
        sha_pop = image_shas_uris_queue.get()
        try:
            for sha_256, sha_uri in sha_pop.items():
                labels = get_labels_from_image(sha_256, sha_uri)
                _cache_container_images_labels(sha_256, labels)
        except Exception:
            # We do not care about the error, but we want to continue
            # our daemon worker.
            pass

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
    #    TODO_1: Do not add to queue if already there
    #    with skopeo_lock:
    #        if sha_256 in sha_in_queue:
    #            return
    logging.debug(f"Adding SHA256 to the SKOPEO queue: {sha_256}")
    image_shas_uris_queue.put({sha_256: image_uri})


def _set_commit_metadata(
    pod: ResourceField,
    date_label: str,
    hash_label: str,
    sha_256: str,
    date_format: str = None,
) -> None:
    with image_label_cache_lock:
        labels = image_label_cache.get(sha_256, None)
        if labels and isinstance(labels, Tuple) and isinstance(labels[0], dict):
            pod.metadata.commit_hash = labels[0].get(hash_label)
            commit_time = labels[0].get(date_label)
            if commit_time:
                try:
                    pod.metadata.commit_timestamp = to_epoch_from_string(
                        commit_time
                    ).timestamp()
                except (ValueError, AttributeError):
                    try:
                        # Do nothing here as we tried with EPOCH timestamp
                        pod.metadata.commit_timestamp = parse_guessing_timezone_DYNAMIC(
                            commit_time, format=date_format
                        ).timestamp()
                    except ValueError:
                        logging.debug(f"Can't get commit timestamp for sha: {sha_256}")


@define(kw_only=True)
class ContainerImageCommitCollector(AbstractCommitCollector):
    date_format: str

    date_annotation_name: str = CommitMetric._ANNOTATION_MAPPIG["commit_time"]
    hash_annotation_name: str = CommitMetric._ANNOTATION_MAPPIG["commit_hash"]

    def get_commit_time(self, metric) -> Optional[CommitMetric]:
        return super().get_commit_time(metric)

    # overrides collector_base.generate_metric()
    def generate_metrics(self) -> Iterable[CommitMetric]:
        metrics = []

        namespaces = get_and_log_namespaces(
            self.kube_client, self.namespaces, self.prod_label
        )

        if not namespaces:
            return metrics

        logging.debug("generate_metrics: start")

        _clear_cleanup_set()

        pods = get_running_pods(self.kube_client, namespaces, self.app_label)

        # Build dictionary with controllers and retrieved pods
        replica_pods_dict = filter_pods_by_replica_uid(pods)

        for pod in replica_pods_dict.values():
            # Since a commit will be built into a particular image and there could be multiple
            # containers (images) per pod, we will push one metric per image/container in the
            # pod template
            images = get_images_from_pod(pod)

            for sha, image_uri in images.items():
                _add_to_cleanup_set(sha)
                _add_image_to_get_label_queue(sha, image_uri)
                _set_commit_metadata(
                    pod,
                    self.date_annotation_name,
                    self.hash_annotation_name,
                    sha,
                    self.date_format,
                )
                if pod.metadata.commit_timestamp and pod.metadata.commit_hash:
                    metric = CommitMetric(
                        name=pod.metadata.labels[self.app_label],
                        namespace=pod.metadata.namespace,
                        labels=pod.metadata.labels,
                        commit_hash=pod.metadata.commit_hash,
                        commit_timestamp=pod.metadata.commit_timestamp,
                        image_hash=sha,
                    )
                    yield metric

        _cleanup_cache()

import logging
import re
import threading
import time
from collections import OrderedDict
from datetime import datetime
from typing import Optional

from kubernetes.dynamic import DynamicClient, ResourceInstance
from kubernetes.dynamic.exceptions import DynamicApiError, ResourceNotFoundError
from kubernetes.dynamic.resource import ResourceField
from prometheus_client import Counter, Gauge

from pelorus.timeutil import ISO_ZULU_FMT, parse_assuming_utc

_k8s_api_errors = Counter(
    "pelorus_k8s_api_errors_total",
    "Total Kubernetes API errors during object lookups",
    ["operation"],
)
_k8s_parent_cache_size = Gauge(
    "pelorus_k8s_parent_cache_size",
    "Current number of entries in the Kubernetes parent object cache",
)

SUPPORTED_REPLICA_OBJECTS = ["ReplicaSet", "ReplicationController"]
_SUPPORTED_REPLICA_OBJECTS_SET = frozenset(SUPPORTED_REPLICA_OBJECTS)

# Cache threshold in seconds, used by every cached_parents_dict entry
CACHE_THRESHOLD_1_DAY = 60 * 60 * 24
_CACHE_MAX_SIZE = 10_000
cached_parents_dict: OrderedDict[str, tuple[ResourceInstance, float]] = OrderedDict()
_cache_lock = threading.Lock()

# Pre-compiled regex for container image URI parsing
_CONTAINER_IMAGE_URI_RE = re.compile(
    r"^(?P<registry>[^/]+/[^/]+/)?(?P<image_name>[^@]+)@(?P<sha256_value>sha256:[a-fA-F0-9]{64})$"
)

# Throttle cache expiration scans to at most once per minute
_last_expiration_time: float = 0.0
_EXPIRATION_INTERVAL = 60.0


def _add_object_to_cache(uid: str, k8s_obj: ResourceInstance) -> None:
    """Cache a K8S object by UID. Entries expire after CACHE_THRESHOLD_1_DAY."""
    now = time.time()
    with _cache_lock:
        if uid not in cached_parents_dict:
            if len(cached_parents_dict) >= _CACHE_MAX_SIZE:
                cached_parents_dict.popitem(last=False)
            cached_parents_dict[uid] = (k8s_obj, now)
            _k8s_parent_cache_size.set(len(cached_parents_dict))


def _get_object_from_cache(uid: str) -> Optional[ResourceInstance]:
    with _cache_lock:
        entry = cached_parents_dict.get(uid)
        if entry is not None:
            cached_parents_dict.move_to_end(uid)
            return entry[0]
    return None


def _remove_expired_objects() -> None:
    """
    Cleanup function to remove expired objects from the cache.
    Throttled to run at most once per _EXPIRATION_INTERVAL seconds.
    """
    global _last_expiration_time

    # Fast path: skip lock when interval hasn't elapsed (float read is atomic under GIL)
    if time.time() - _last_expiration_time < _EXPIRATION_INTERVAL:
        return

    with _cache_lock:
        current_time = time.time()

        if current_time - _last_expiration_time < _EXPIRATION_INTERVAL:
            return

        _last_expiration_time = current_time

        while cached_parents_dict:
            uid = next(iter(cached_parents_dict))
            if current_time - cached_parents_dict[uid][1] <= CACHE_THRESHOLD_1_DAY:
                break
            del cached_parents_dict[uid]

        _k8s_parent_cache_size.set(len(cached_parents_dict))


def convert_datetime(dt: str | datetime) -> datetime:
    """Attrs converter: parse an ISO 8601 Zulu string to a UTC datetime, or pass through."""
    if isinstance(dt, datetime):
        return dt
    return parse_assuming_utc(dt, ISO_ZULU_FMT)


def get_running_pods(
    client: DynamicClient,
    namespaces: Optional[set[str]] = None,
    app_label: Optional[str] = None,
    with_owner_only: bool = True,
) -> list[ResourceField]:
    """
    Retrieves running pods in the cluster, optionally filtering
    to only those with a ReplicaSet or ReplicationController owner.

    If namespaces are provided, only those namespaces are queried.
    If `app_label` is provided, only pods matching that label selector are returned.

    Args:
        client (DynamicClient): A Kubernetes dynamic client.
        namespaces (Optional[set[str]]): Namespaces for which to discover pods. If not provided,
                                         the function retrieves pods in all namespaces.
        app_label (Optional[str]): A label selector used to filter pods (e.g. "app.kubernetes.io/name").
                                   By default, no label filter is applied.
        with_owner_only (bool): If True (default), return only pods owned by a ReplicaSet or
                                ReplicationController. If False, return all running pods.
    """

    v1_pods = client.resources.get(api_version="v1", kind="Pod")

    pods = []

    for ns in namespaces or {""}:
        items = v1_pods.get(
            label_selector=app_label,
            field_selector="status.phase=Running",
            namespace=ns,
        ).items
        if with_owner_only:
            for pod in items:
                if pod.metadata.ownerReferences and any(
                    ref.kind in _SUPPORTED_REPLICA_OBJECTS_SET
                    for ref in pod.metadata.ownerReferences
                ):
                    pods.append(pod)
        else:
            pods.extend(items)

    logging.debug("Found %d running pods across %d namespace(s)", len(pods), len(namespaces or {""}))
    return pods


def get_owner_object_from_child(
    client: DynamicClient, uid: str, child_object: ResourceField
) -> dict[str, ResourceInstance]:
    """
    Retrieves the parent Kubernetes object by matching the given UID
    against the child's ownerReferences.

    Args:
        client (DynamicClient): A Kubernetes dynamic client.
        uid (str): The UID to match in the child's ownerReferences.
        child_object (ResourceField): The child object whose ownerReferences are searched.

    Returns:
        dict[str, ResourceInstance]: {uid: parent_object}, or empty dict if not found.
    """

    owner_ref = next(
        (owner for owner in child_object.metadata.ownerReferences if owner.uid == uid),
        None,
    )

    if owner_ref:
        _remove_expired_objects()
        replica = _get_object_from_cache(owner_ref.uid)
        if replica:
            return {owner_ref.uid: replica}

        logging.debug(
            "Getting replica: %s, kind: %s, api_version: %s",
            owner_ref.uid,
            owner_ref.kind,
            owner_ref.apiVersion,
        )

        try:
            api_resource = client.resources.get(
                api_version=owner_ref.apiVersion, kind=owner_ref.kind
            )

            # field_selector does not work on UID, so we match by name+namespace
            # and verify UID separately
            replica_list = api_resource.get(
                field_selector=f"metadata.name={owner_ref.name}",
                namespace=child_object.metadata.namespace,
            )

            for replica in replica_list.items:
                if replica.metadata.uid == owner_ref.uid:
                    _add_object_to_cache(owner_ref.uid, replica)
                    return {owner_ref.uid: replica}
        except ResourceNotFoundError:
            _k8s_api_errors.labels(operation="get_owner_object").inc()
            logging.debug(
                "API Object not found for version: %s object: %s",
                owner_ref.apiVersion,
                owner_ref.uid,
            )
        except DynamicApiError:
            _k8s_api_errors.labels(operation="get_owner_object").inc()
            logging.warning(
                "Failed to retrieve owner object %s (kind=%s, apiVersion=%s) for pod %s/%s",
                owner_ref.uid,
                owner_ref.kind,
                owner_ref.apiVersion,
                child_object.metadata.namespace,
                child_object.metadata.name,
                exc_info=True,
            )
    return {}


def filter_pods_by_replica_uid(
    pods_list: list[ResourceField],
) -> dict[str, ResourceField]:
    """
    Deduplicates pods by their ReplicaSet/ReplicationController owner UID.

    Since pods within a ReplicaSet are identical replicas, we only need
    one representative pod per owner. If a pod has multiple ownerReferences,
    each matching owner gets an entry.

    Args:
        pods_list (list[ResourceField]): A list of Pod objects.

    Returns:
        dict[str, ResourceField]: Owner UID -> one representative pod.
    """
    return {
        owner_reference.uid: pod
        for pod in pods_list
        for owner_reference in pod.metadata.ownerReferences or []
        if hasattr(owner_reference, "uid")
        and owner_reference.kind in _SUPPORTED_REPLICA_OBJECTS_SET
    }


def get_and_log_namespaces(
    client: DynamicClient, namespaces: set[str], prod_label: str
) -> set[str]:
    """
    Get the set of namespaces to watch, and log what they are.
    They will be either:
    1. The namespaces explicitly specified
    2. The namespaces matched by PROD_LABEL
    3. If neither namespaces nor the PROD_LABEL is given, then implicitly matches all namespaces.
    """
    if namespaces:
        logging.debug("Watching namespaces %s", namespaces)
        return namespaces

    if prod_label:
        logging.debug(
            "No namespaces specified, watching all namespaces with given PROD_LABEL (%s)",
            prod_label,
        )
        query_args = dict(label_selector=prod_label)
    else:
        logging.debug(
            "No namespaces specified and no PROD_LABEL given, watching all namespaces."
        )
        query_args = {}

    all_namespaces = client.resources.get(api_version="v1", kind="Namespace")
    namespaces = {ns.metadata.name for ns in all_namespaces.get(**query_args).items}
    logging.debug("Watching namespaces %s", namespaces)
    if not namespaces:
        logging.warning(
            "No NAMESPACES given and PROD_LABEL did not return any matching namespaces."
        )
    return namespaces


def _parse_container_image_uri(
    image_uri: str,
) -> tuple[str, str, str] | tuple[None, None, None]:
    """
    Parses the container image URI and extracts image registry, image name and image SHA256 value.

    Args:
        image_uri (str): Container image URI in the form ``registry/path/image@sha256:...``.
            All three components (registry, image name, SHA256) must be present.

    Returns:
        tuple[str, str, str] | tuple[None, None, None]:
            (registry, image_name, sha256_value), or (None, None, None) if parsing fails.
    """
    match = _CONTAINER_IMAGE_URI_RE.match(image_uri)
    if match:
        registry = match.group("registry")
        image_name = match.group("image_name")
        sha256_value = match.group("sha256_value")
        if registry and image_name and sha256_value:
            return registry, image_name, sha256_value
    else:
        # This may be noisy if there are a lot of pods where the container
        # spec doesn't have a SHA but the status does.
        # But since it's only in debug logs, it doesn't matter.
        logging.debug("Skipping unresolved image reference: %s", image_uri)
    return None, None, None


def get_images_from_pod(pod: ResourceField) -> dict[str, str]:
    """Extract image SHA256 digests from a pod's containerStatuses.

    Returns a dict of ``{sha256_digest: full_image_reference}`` for containers
    whose imageID contains a resolved ``sha256:`` digest.
    """

    image_shas = {}
    if pod and pod.status and pod.status.containerStatuses:
        for container_status in pod.status.containerStatuses:
            image_id = getattr(container_status, "imageID", None)
            if not image_id:
                continue
            registry, image_name, sha256_value = _parse_container_image_uri(image_id)
            if sha256_value is not None:
                image_shas[sha256_value] = f"docker://{registry}{image_name}@{sha256_value}"
    return image_shas

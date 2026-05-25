import logging
import re
import threading
import time
from collections import OrderedDict
from datetime import datetime
from typing import Optional

from kubernetes.dynamic import DynamicClient, ResourceInstance
from kubernetes.dynamic.exceptions import ResourceNotFoundError
from kubernetes.dynamic.resource import ResourceField

from pelorus.timeutil import ISO_ZULU_FMT, parse_assuming_utc

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
    with _cache_lock:
        if uid not in cached_parents_dict:
            if len(cached_parents_dict) >= _CACHE_MAX_SIZE:
                cached_parents_dict.popitem(last=False)
            cached_parents_dict[uid] = (k8s_obj, time.time())


def _get_object_from_cache(uid: str) -> Optional[ResourceInstance]:
    """
    Gets the object from the cache by its uid.
    """
    with _cache_lock:
        entry = cached_parents_dict.get(uid)
        if entry is not None:
            cached_parents_dict.move_to_end(uid)
    if entry is None:
        return None
    return entry[0]


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

        expired_keys = [
            uid
            for uid, (_, insertion_time) in cached_parents_dict.items()
            if current_time - insertion_time > CACHE_THRESHOLD_1_DAY
        ]
        for uid in expired_keys:
            del cached_parents_dict[uid]


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
    Retrieves running pods in the OpenShift cluster that have a parent owner,
    which can be either a ReplicaSet or ReplicationController.

    Optionally the function retrieves the pods by the provided namespaces.
    If the `app_label` parameter is provided, it only returns pods that have a label
    that matches the specified label.

    Args:
        client (DynamicClient): An OpenShift client object.
        namespaces (Optional[Set[str]]): Namespaces for which to discover pods. If not provided,
                                         the function retrieves pods in all namespaces.
        app_label (Optional[str]): A label that a pod must have to be considered production.
                                   By default, no label is required.
        with_owner_only (bool): A flag that determines whether to return only pods with ownerReferences or all pods.
                                By default, the function only returns pods with ownerReferences.

    Returns:
        List[ResourceField]: A list of ResourceField objects representing the running pods in the
                             OpenShift cluster that meet the criteria.
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

    return pods


def get_owner_object_from_child(
    client: DynamicClient, uid: str, child_object: ResourceField
) -> dict[str, ResourceInstance]:
    """
    Retrieves the OpenShift Parent object by its UID, using information about the API version and resource type
    from the given Child object.

    Args:
        client (DynamicClient): An OpenShift client object.
        uid (str): The UID of the Parent object.
        child_object (ResourceField): The Child object that contains the reference to the Parent object.

    Returns:
        Dict[str, ResourceInstance]: A dictionary with the UID of the Parent object as the key
                                     and the Parent object itself as the value.
                                     An empty dictionary is returned if the Parent object is not found
                                     or if there is an error during the retrieval.
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
            logging.debug(
                "API Object not found for version: %s object: %s",
                owner_ref.apiVersion,
                owner_ref.uid,
            )
        except Exception:
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
    Filters out the given list of Pod objects to create a dictionary with ReplicaSet or
    ReplicationController UIDs as keys.

    In OpenShift, one Pod may have multiple ownerReferences. This function filters the list of
    Pod objects to identify unique ReplicaSet or ReplicationController objects based on their UID,
    which is stored in the ownerReferences attribute of the Pod object.

    Since Pods within a ReplicaSet are homogeneous and identical replicas,
    we can filter out unique ReplicaSet objects even if multiple Pods are deployed.

    Args:
        pods_list (List[ResourceField]): A list of Pod objects.

    Returns:
        Dict[str, ResourceField]
                A dictionary with ReplicaSet or ReplicationController UIDs as keys and Pod objects as values.
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
        query_args = dict()

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
        image_uri[str]: Container image URI.
            Expected is an URI with registry URI and SHA256 value.

    Returns:
        tuple[str, str, str]
            Parsed container URI into tuple of registry URI, image name and SHA256 value.
            If any of the expected values is not found it then returns (None, None, None).
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
    """
    Get the image with its sha256 from the pod (imageID). The parent object such as
    ReplicaSet may contain only image reference by label and not the unique
    sha256, which isn't ideal, so we need to aggregate the images from the
    running pods and corresponding parent objects.
    """

    image_shas = {}
    if pod and pod.status and pod.status.containerStatuses:
        for container_status in pod.status.containerStatuses:
            image_id = container_status.imageID
            registry, image_name, sha256_value = _parse_container_image_uri(image_id)
            if sha256_value and registry and image_name:
                image_shas[
                    sha256_value
                ] = f"docker://{registry}{image_name}@{sha256_value}"
    return image_shas

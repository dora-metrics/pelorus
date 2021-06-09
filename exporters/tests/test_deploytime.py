from datetime import datetime, timedelta
from random import randrange
from typing import Any
from unittest.mock import NonCallableMock

from openshift.dynamic import DynamicClient  # type: ignore
from openshift.dynamic.discovery import Discoverer  # type: ignore

import pelorus
from deploytime.app import DeployTimeMetric, generate_metrics  # type: ignore
from tests.openshift_mocks import *
# pylama:ignore=W0401

APP_LABEL = pelorus.get_app_label()


def test_generate_metrics() -> None:
    FOO_NS = "foo_ns"
    BAR_NS = "bar_ns"
    # region set up mocks
    mock_client = NonCallableMock(DynamicClient)
    pods_mock = NonCallableMock(Discoverer)
    replicas_mock = NonCallableMock(Discoverer)

    def get_resource(*, kind: str, **_kwargs):
        if kind == "Pod":
            return pods_mock
        elif kind.startswith("Replica"):
            return replicas_mock
        raise ValueError(f"Unknown, un-mocked resource kind '{kind}'")

    mock_client.resources.get.side_effect = get_resource

    def rc(
        name: str,
        namespace: str,
        app_label: str,
        creationTimestamp: Any,
        labels: dict[str, str] = None,
    ) -> ReplicationController:
        """create a ReplicationController with appropriate metadata"""
        labels = labels or {}
        labels[APP_LABEL] = app_label
        return ReplicationController(
            Metadata(
                name=name,
                namespace=namespace,
                labels=labels,
                creationTimestamp=creationTimestamp,
            )
        )

    def random_time() -> datetime:
        return datetime.now() - timedelta(hours=12) + timedelta(hours=randrange(0, 12))

    foo_rs = rc("foo_rc", FOO_NS, "foo_app", random_time(), dict(foo_label="bar"))
    bar_rc = rc("bar_rc", BAR_NS, "bar_app", random_time())

    replicas_mock.get.return_value = ResourceGetResponse.of(foo_rs, bar_rc)

    def pod(namespace: str, owner_refs: list[OwnerRef], container_shas: list[str]):
        return Pod(
            metadata=Metadata(namespace=namespace, ownerReferences=owner_refs),
            spec=PodSpec(containers=[Container(x) for x in container_shas]),
        )

    pods: ResourceGetResponse[Pod] = ResourceGetResponse.of(
        pod(
            "foo_ns", [OwnerRef("ReplicaSet", "foo_rc")], ["sha256:FOO_POD_IMAGE_1_SHA"]
        ),
        pod(
            "bar_ns",
            [OwnerRef("ReplicationController", "bar_rc")],
            ["sha256:BAR_POD_IMAGE_1_SHA"],
        ),
    )
    pods_mock.get.return_value = pods
    # endregion

    expected: list[DeployTimeMetric] = [
        DeployTimeMetric(
            name="foo_app",
            namespace="foo_ns",
            labels={"foo_label": "bar", APP_LABEL: "foo_app"},
            deploy_time=foo_rs.metadata.creationTimestamp,
            image_sha="sha256:FOO_POD_IMAGE_1_SHA",
        ),
        DeployTimeMetric(
            name="bar_app",
            namespace="bar_ns",
            labels={APP_LABEL: "bar_app"},
            deploy_time=bar_rc.metadata.creationTimestamp,
            image_sha="sha256:BAR_POD_IMAGE_1_SHA",
        ),
    ]

    actual = generate_metrics(namespaces=[FOO_NS, BAR_NS], dyn_client=mock_client)

    assert actual == expected

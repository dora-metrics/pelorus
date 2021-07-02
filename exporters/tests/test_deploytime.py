from collections import defaultdict
from datetime import datetime, timedelta
from random import randrange
from typing import Any, Sequence
from unittest.mock import NonCallableMock

import pytest
from deploytime.app import DeployTimeMetric, generate_metrics, image_sha  # type: ignore
from openshift.dynamic import DynamicClient  # type: ignore
from openshift.dynamic.discovery import Discoverer  # type: ignore
from tests.openshift_mocks import *

import pelorus

# pylava:ignore=W0401

# region test constants
APP_LABEL = pelorus.get_app_label()

FOO_NS = "foo_ns"
BAR_NS = "bar_ns"
BAZ_NS = "baz_ns"

FOO_APP = "foo_app"
BAR_APP = "bar_app"

FOO_LABEL = "foo_label"
FOO_LABEL_VALUE = "test"

REPLICA_SET = "ReplicaSet"
REP_CONTROLLER = "ReplicationController"
UNKNOWN_OWNER_KIND = "UnknownOwnerKind"

FOO_REP = "foo_rc"
FOO_REP_KIND = REP_CONTROLLER
BAR_REP = "bar_rs"
BAR_REP_KIND = REPLICA_SET
BAZ_REP = "baz_unknown"
BAZ_REP_KIND = UNKNOWN_OWNER_KIND
QUUX_REP_KIND = REPLICA_SET

FOO_POD_SHAS = [
    "sha256:b4465ee3a99034c395ad4296b251cbe8d12f1676a107e942f9f543a185d67b2b"
]
BAR_POD_SHAS = [
    "sha256:90663c4a9ac6cd3eb1889e1674dea13cdd4490adb70440a789acf70d4c0c2c75",
    "I am not a valid sha!",
]
BAZ_POD_SHAS = ["I'm not valid either but it'll never matter"]
QUUX_POD_SHAS = [
    "sha256:12257fefdca6298ecc4030468ba37663a57700e4d8061a5b1ca453cfe8339f59"
]
# endregion

# region mock data creation helpers


@attr.define(slots=False)
class DynClientMockData:
    pods: Sequence[Pod]
    replicators: Sequence[Replicator]

    def __attrs_post_init__(self):
        self.mock_client = NonCallableMock(DynamicClient)
        self.pods_mock = NonCallableMock(Discoverer)
        self.replicators_by_kind = defaultdict(lambda: NonCallableMock(Discoverer))

        self.mock_client.resources.get.side_effect = self.get_resource
        self.pods_mock.get.side_effect = self.get_pods

        for rep in self.replicators:
            mock = self.replicators_by_kind[rep.kind]
            if not isinstance(mock.get.return_value, list):
                mock.get.return_value = ResourceGetResponse([])
            mock.get.return_value.items.append(rep)

    def get_resource(self, *, kind: str, **_kwargs):
        if kind == "Pod":
            return self.pods_mock
        elif kind.startswith("Replica"):
            return self.replicators_by_kind[kind]
        raise ValueError(f"Unknown, un-mocked resource kind '{kind}'")

    def get_pods(self, **_kwargs):
        return ResourceGetResponse(self.pods)

    def get_replicas(self, *, kind: str, **_kwargs):
        return ResourceGetResponse([x for x in self.replicators if x.kind == kind])


def rc(
    kind: str,
    name: str,
    namespace: str,
    app_label: str,
    creationTimestamp: datetime,
    labels: dict[str, str] = None,
) -> Replicator:
    """create a Replicator with appropriate metadata"""
    labels = labels or {}
    labels[APP_LABEL] = app_label
    return Replicator(
        kind=kind,
        metadata=Metadata(
            name=name,
            namespace=namespace,
            labels=labels,
            creationTimestamp=creationTimestamp,
        ),
    )


def random_time() -> datetime:
    return datetime.now() - timedelta(hours=12) + timedelta(hours=randrange(0, 12))


def pod(namespace: str, owner_refs: list[OwnerRef], container_shas: list[str]):
    return Pod(
        metadata=Metadata(namespace=namespace, ownerReferences=owner_refs),
        spec=PodSpec(containers=[Container(x) for x in container_shas]),
    )


# endregion


def test_generate_normal_case() -> None:
    foo_rep = rc(
        FOO_REP_KIND,
        FOO_REP,
        FOO_NS,
        FOO_APP,
        random_time(),
        {FOO_LABEL: FOO_LABEL_VALUE},
    )
    bar_rep = rc(BAR_REP_KIND, BAR_REP, BAR_NS, BAR_APP, random_time())

    pods = [
        pod(FOO_NS, [foo_rep.ref()], FOO_POD_SHAS),
        pod(BAR_NS, [bar_rep.ref()], BAR_POD_SHAS),
        # case: pod with unsupported rep kind
        pod(FOO_NS, [OwnerRef(BAZ_REP_KIND, BAZ_REP)], FOO_POD_SHAS),
        # case: pod references rep we don't have an entry for
        pod(FOO_NS, [OwnerRef(FOO_REP_KIND, "Unknown Rep")], FOO_POD_SHAS),
        # case: pod in NS we don't care about
        pod(BAZ_NS, [OwnerRef(BAZ_REP_KIND, BAZ_REP)], BAZ_POD_SHAS),
    ]

    data = DynClientMockData(pods=pods, replicators=[foo_rep, bar_rep])

    expected: list[DeployTimeMetric] = [
        DeployTimeMetric(
            name=FOO_APP,
            namespace=FOO_NS,
            labels={FOO_LABEL: FOO_LABEL_VALUE, APP_LABEL: FOO_APP},
            deploy_time=foo_rep.metadata.creationTimestamp,
            image_sha=FOO_POD_SHAS[0],
        ),
        DeployTimeMetric(
            name=BAR_APP,
            namespace=BAR_NS,
            labels={APP_LABEL: BAR_APP},
            deploy_time=bar_rep.metadata.creationTimestamp,
            image_sha=BAR_POD_SHAS[0],
        ),
    ]

    actual = list(
        generate_metrics(namespaces=[FOO_NS, BAR_NS], dyn_client=data.mock_client)
    )

    assert actual == expected


@pytest.mark.xfail(reason="Bug with different rep kinds with same name and namespace")
# when fixed, we should just roll this case into the others(?)
def test_generate_reps_with_same_name() -> None:
    foo_rep = rc(
        FOO_REP_KIND,
        FOO_REP,
        FOO_NS,
        FOO_APP,
        random_time(),
        {FOO_LABEL: FOO_LABEL_VALUE},
    )
    bar_rep = rc(BAR_REP_KIND, BAR_REP, BAR_NS, BAR_APP, random_time())
    assert FOO_REP_KIND != QUUX_REP_KIND
    quux_rep = rc(QUUX_REP_KIND, FOO_REP, FOO_NS, "N/A", random_time())

    pods = [
        pod(FOO_NS, [foo_rep.ref()], FOO_POD_SHAS),
        pod(BAR_NS, [bar_rep.ref()], BAR_POD_SHAS),
        pod(BAZ_NS, [], BAZ_POD_SHAS),
    ]

    data = DynClientMockData(pods=pods, replicators=[foo_rep, bar_rep, quux_rep])

    expected: list[DeployTimeMetric] = [
        DeployTimeMetric(
            name=FOO_APP,
            namespace=FOO_NS,
            labels={FOO_LABEL: FOO_LABEL_VALUE, APP_LABEL: FOO_APP},
            deploy_time=foo_rep.metadata.creationTimestamp,
            image_sha=FOO_POD_SHAS[0],
        ),
        DeployTimeMetric(
            name=BAR_APP,
            namespace=BAR_NS,
            labels={APP_LABEL: BAR_APP},
            deploy_time=bar_rep.metadata.creationTimestamp,
            image_sha=BAR_POD_SHAS[0],
        ),
    ]

    actual = list(
        generate_metrics(namespaces=[FOO_NS, BAR_NS], dyn_client=data.mock_client)
    )

    assert actual == expected


def test_image_sha() -> None:
    SHA = "sha256:09d255154fe1e47b8d409130ae5db664d64a935b9845c5106d755b2837afa5ff"
    assert image_sha(SHA) == SHA

    assert image_sha("not a sha") is None

#!/usr/bin/env python

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Generator, NewType, Protocol

from attrs import asdict, define, field, frozen
from kubernetes.dynamic import Resource, ResourceInstance
from kubernetes.dynamic.exceptions import ResourceNotFoundError
from openshift.dynamic import DynamicClient

import pelorus
import pelorus.utils
from pelorus.utils import paginate_resource

DOCS_BASE_URL = "https://pelorus.readthedocs.io/en/stable/"
DEPLOYTIME_PREPARE_DATA_URL = DOCS_BASE_URL + "GettingStarted#preparing-your-data"
COMMITTIME_PREPARE_DATA_URL = DOCS_BASE_URL + "GettingStarted#commit-time"

# A NOTE ON TERMINOLOGY:
# what you might call a "resource" in openshift is called a ResourceInstance by the client.
# to the client, a Resource is its "type definition".
# Remember, they're called CustomResourceDefinitions, not CustomResourceTypeDefinitions.

# region: identifier helpers and wrappers


@frozen
class ResourceKind:
    """
    The "type" of a resource.
    """

    apiVersion: str
    kind: str

    def __str__(self):
        return f"{self.apiVersion}/{self.kind}"


@frozen
class ResourceIdentifier:
    """
    A way to fully identify a resource instance in the OpenShift cluster.
    """

    apiVersion: str
    kind: str
    namespace: str
    name: str

    @classmethod
    def from_instance(cls, inst: ResourceInstance):
        return cls(
            inst.apiVersion, inst.kind, inst.metadata.namespace, inst.metadata.name
        )

    @property
    def kind_(self):
        return ResourceKind(self.apiVersion, self.kind)


PodId = NewType("PodId", ResourceIdentifier)
ReplicatorId = NewType("ReplicatorId", ResourceIdentifier)
OwnedPods = NewType("OwnedPods", set[PodId])
"""
Pods owned by a replicator.
"""
BuildId = NewType("BuildId", ResourceIdentifier)

# endregion

APP_LABEL = pelorus.get_app_label()


@define
class Troubleshooter:
    client: DynamicClient
    namespace: str

    pods: Resource = field(init=False)
    replicators_by_kind: dict[ResourceKind, Resource] = field(init=False, factory=dict)
    builds: Resource = field(init=False)

    def __attrs_post_init__(self):
        self.pods = self.client.resources.get(api_version="v1", kind="Pod")

        for version, kind in [
            ("v1", "ReplicationController"),
            ("apps/v1", "ReplicaSet"),
            ("extensions/v1beta1", "ReplicaSet"),
        ]:
            try:
                res_type = ResourceKind(version, kind)
                self.replicators_by_kind[res_type] = self.client.resources.get(
                    api_version=version, kind=kind
                )
            except ResourceNotFoundError:
                pass

        self.builds = self.client.resources.get(
            api_version="build.openshift.io/v1", kind="Build"
        )

    def pods_missing_app_label(self) -> Generator[PodId, None, None]:
        """
        Pods missing the required app label.
        """
        for pod in paginate_resource(
            self.pods,
            query=dict(
                label_selector=f"!{APP_LABEL}",
                field_selector="status.phase=Running",
                namespace=namespace,
            ),
        ):
            yield PodId(ResourceIdentifier.from_instance(pod))

    def replicators_missing_app_label(self) -> dict[ReplicatorId, OwnedPods]:
        """
        Pods that are correctly labeled, but their replicator is not.

        TODO: do we also check for mismatched labels?
        """

        seen_good_replicators: set[ReplicatorId] = set()
        replicator_to_pod: dict[ReplicatorId, OwnedPods] = {}

        for pod in paginate_resource(
            self.pods,
            query=dict(
                label_selector=APP_LABEL,
                field_selector="status.phase=Running",
                namespace=namespace,
            ),
        ):
            for owner in pod.metadata.ownerReferences:
                rep_id = ReplicatorId(
                    ResourceIdentifier(
                        owner.apiVersion, owner.kind, namespace, owner.name
                    )
                )

                if rep_id in seen_good_replicators:
                    continue

                if rep_id in replicator_to_pod:
                    replicator_to_pod[rep_id].add(
                        PodId(ResourceIdentifier.from_instance(pod))
                    )
                    continue

                replicator_resource = self.replicators_by_kind.get(rep_id.kind_)

                if replicator_resource is None:
                    # unknown kind
                    continue

                replicator_instance = client.get(
                    replicator_resource, namespace=namespace, name=rep_id.name
                )

                if getattr(replicator_instance.metadata.labels, APP_LABEL, None):
                    seen_good_replicators.add(rep_id)
                    continue

                replicator_to_pod.setdefault(rep_id, OwnedPods(set())).add(
                    PodId(ResourceIdentifier.from_instance(pod))
                )

        return replicator_to_pod

    def builds_with_missing_app_labels(self) -> Generator[BuildId, None, None]:
        # TODO: missing required metadata as well
        for build in paginate_resource(
            self.builds, query=dict(label_selector=f"!{APP_LABEL}", namespace=namespace)
        ):
            yield BuildId(ResourceIdentifier.from_instance(build))


# endregion

# region: reports


class Report(Protocol):
    def print_human_readable(self):
        ...

    def to_json(self) -> dict:
        ...


@frozen
class DeploytimeTroubleshootingReport:
    app_label: str = field(default=APP_LABEL, init=False)
    duration: timedelta

    pods_missing_app_label: list[PodId]
    replicators_missing_app_label: dict[ReplicatorId, OwnedPods]

    @property
    def anything_to_report(self):
        return self.pods_missing_app_label or self.replicators_missing_app_label

    def _print_pods(self):
        if not self.pods_missing_app_label:
            print("No pods were missing the app label", self.app_label)
            return

        print("The following pods were missing the label", self.app_label)
        for pod in self.pods_missing_app_label:
            print(" ", pod.name)

    def _print_replicators(self):
        if not self.replicators_missing_app_label:
            print("No replicators were missing the label", self.app_label)
            return

        print("The following replicators were missing the label", self.app_label)

        for replicator in self.replicators_missing_app_label:
            print(" ", replicator.kind_, replicator.name)

    def _print_suggestion(self):
        print(f"Add the label {self.app_label}.")
        print("See", DEPLOYTIME_PREPARE_DATA_URL)

    def print_human_readable(self):
        self._print_pods()
        print()
        self._print_replicators()
        if self.anything_to_report:
            self._print_suggestion()

    def to_json(self) -> dict:
        pods_missing_label = [pod.name for pod in self.pods_missing_app_label]
        reps_missing_label = [
            asdict(rep, value_serializer=asdict_serializer)
            | dict(pods=[pod.name for pod in pods])
            for rep, pods in self.replicators_missing_app_label.items()
        ]
        return dict(
            namespace=namespace,
            app_label=self.app_label,
            duration=self.duration.total_seconds(),
            pods_missing_app_label=pods_missing_label,
            replicators_missing_app_label=reps_missing_label,
        )

    @classmethod
    def troubleshoot(cls, troubleshooter: Troubleshooter):
        start = datetime.now()
        pods = list(troubleshooter.pods_missing_app_label())
        replicators = troubleshooter.replicators_missing_app_label()
        duration = datetime.now() - start

        return cls(duration, pods, replicators)


@frozen
class CommittimeTroubleshootingReport:
    app_label: str = field(default=APP_LABEL, init=False)
    duration: timedelta

    builds_missing_app_label: list[BuildId]

    @property
    def anything_to_report(self):
        return bool(self.builds_missing_app_label)

    def print_human_readable(self):
        if not self.builds_missing_app_label:
            print("No builds were missing the app label", self.app_label)
            return

        print("The following builds were missing the app label", self.app_label)
        for build in self.builds_missing_app_label:
            print(build.name)

        # TODO: app label committime docs?

    def to_json(self) -> dict:
        return dict(
            namespace=namespace,
            app_label=self.app_label,
            duration=self.duration.total_seconds(),
            builds_missing_app_label=[
                asdict(build) for build in self.builds_missing_app_label
            ],
        )

    @classmethod
    def troubleshoot(cls, troubleshooter: Troubleshooter):
        start = datetime.now()
        builds = list(troubleshooter.builds_with_missing_app_labels())
        duration = datetime.now() - start

        return cls(duration, builds)


def asdict_serializer(_inst, _attr, value):
    """
    Serializes certain types specially when using attrs.asdict.
    """
    if isinstance(value, ResourceKind):
        return str(value)
    return value


reports_by_name = dict(
    deploytime=DeploytimeTroubleshootingReport,
    committime=CommittimeTroubleshootingReport,
)

# endregion

# region: main
parser = argparse.ArgumentParser(
    description=f"""Troubleshoot resources that are not appearing in pelorus.
    To set the app label to search, set the environment variable APP_LABEL. Defaults to {pelorus.DEFAULT_APP_LABEL}"""
)
parser.add_argument(
    "--namespace", "-n", required=True, help="Which namespace to look in."
)
parser.add_argument(
    "--output",
    "-o",
    choices=["human", "json"],
    default="human",
    help="The output format: human readable (default), or json",
)
parser.add_argument(
    "--for-exporter",
    nargs="+",
    choices=["deploytime", "committime"],
    default=["deploytime"],
    help="Which exporters to check information for. Can pass multiple. Defaults to deploytime.",
)

if __name__ == "__main__":
    args = parser.parse_args()

    namespace = args.namespace
    client = pelorus.utils.get_k8s_client()

    troubleshooter = Troubleshooter(client, namespace)

    # because we need to support both json and human output,
    # and running multiple reports, we have two steps:
    # "collect" the output for each report, and then finalize.

    if args.output == "human":
        pelorus.setup_logging()

        def collect_output(report_name: str, report: Report):
            report.print_human_readable()

        def finalize():
            pass

    elif args.output == "json":
        outputs = {}

        def collect_output(report_name: str, report: Report):
            outputs[report_name] = report.to_json()

        def finalize():
            json.dump(outputs, fp=sys.stdout)

    else:
        sys.exit(f"Unknown output format {args.output}")

    for report_type in set(args.for_exporter):
        report = reports_by_name[report_type].troubleshoot(troubleshooter)

        collect_output(report_type, report)

    finalize()

# endregion

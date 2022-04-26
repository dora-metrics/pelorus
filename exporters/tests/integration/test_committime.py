from __future__ import annotations

from typing import Optional

import attr
import pytest
from kubernetes.client import ApiClient, Configuration
from openshift.dynamic import DynamicClient

from committime import CommitMetric
from committime.collector_github import GitHubCommitCollector


def setup_collector():
    kube_config = Configuration()
    kube_config.host = "https://localhost:3000"
    kube_config.verify_ssl = False
    dyn_client = DynamicClient(ApiClient(configuration=kube_config))

    username = "gituser"
    token = "gittoken"
    git_api = "localhost:3000"
    namespaces = (
        "basic-nginx-build,basic-nginx-dev,basic-nginx-stage,basic-nginx-prod".split(
            ","
        )
    )
    apps = None
    tls_verify = False
    return GitHubCommitCollector(
        dyn_client, username, token, namespaces, apps, git_api, tls_verify
    )


def expected_commits() -> list[CommitMetricEssentials]:
    metrics = [
        CommitMetricEssentials(
            commit_timestamp=1619381788.0,
            namespace="basic-nginx-build",
            name="basic-nginx",
            commit_hash="15dedb60b6208aafdfb2328a93543e3d94500978",
            image_hash="sha256:c1282f65b5c327db4dcc6cdfb27e91338bd625d119d9ae769318f089d82e35e2",
        ),
        CommitMetricEssentials(
            commit_timestamp=1619381788.0,
            namespace="basic-nginx-build",
            name="basic-nginx",
            commit_hash="15dedb60b6208aafdfb2328a93543e3d94500978",
            image_hash="sha256:4a20c8cfa48af3a938462e9cd7bfa0b16abfbc6ba16f0999f3931c79b1130e4b",
        ),
        CommitMetricEssentials(
            commit_timestamp=1620401174.0,
            namespace="basic-nginx-build",
            name="basic-nginx",
            commit_hash="620ce8b570c644338ba34224fc09b2d8a30bca02",
            image_hash="sha256:71309995e6da43b76079a649b00e0aa8378443e72f1fccc76af0d73d67a7f644",
        ),
    ]
    metrics.sort(key=lambda commit: commit.commit_timestamp)
    return metrics


@attr.define
class CommitMetricEssentials:
    name: str = attr.field()
    namespace: Optional[str] = attr.field(default=None, kw_only=True)

    commit_hash: Optional[str] = attr.field(default=None, kw_only=True)
    commit_timestamp: Optional[float] = attr.field(default=None, kw_only=True)

    image_hash: Optional[str] = attr.field(default=None, kw_only=True)

    @staticmethod
    def from_commit_metric(cm: CommitMetric) -> CommitMetricEssentials:
        args = {
            key: getattr(cm, key)
            for key in "name namespace commit_hash commit_timestamp image_hash".split()
        }

        return CommitMetricEssentials(**args)


@pytest.mark.mockoon
def test_github_provider():
    collector = setup_collector()

    actual = [
        CommitMetricEssentials.from_commit_metric(cm)
        for cm in collector.generate_metrics()
    ]

    actual.sort(key=lambda commit: commit.commit_timestamp)

    assert actual == expected_commits()

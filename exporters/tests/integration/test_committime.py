from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

import pytest
from kubernetes.client import ApiClient, Configuration
from openshift.dynamic import DynamicClient

from committime import CommitMetric
from committime.app import GitCommittimeConfig
from committime.collector_github import GitHubCommitCollector
from pelorus.config import load_and_log


def _make_dyn_client():
    kube_config = Configuration()
    kube_config.host = "https://localhost:3000"
    kube_config.verify_ssl = False
    return DynamicClient(ApiClient(configuration=kube_config))


USERNAME = "gituser"
TOKEN = "gittoken"
GIT_API = "localhost:3000"
NAMESPACES = "basic-nginx-build,basic-nginx-dev,basic-nginx-stage,basic-nginx-prod"


def setup_collector_from_env_loading():
    env = dict(
        API_USER=USERNAME,
        TOKEN=TOKEN,
        NAMESPACES=NAMESPACES,
        GIT_API=GIT_API,
        GIT_PROVIDER="github",
    )

    config = load_and_log(
        GitCommittimeConfig,
        other=dict(
            kube_client=_make_dyn_client(),
            tls_verify=False,
        ),
        env=env,
    )

    return cast(GitHubCommitCollector, config.make_collector())


def expected_commits() -> list[CommitMetric]:
    metrics = [
        CommitMetric(
            commit_timestamp=datetime.fromtimestamp(1619381788.0, tz=timezone.utc),
            namespace="basic-nginx-build",
            name="basic-nginx",
            commit_hash="15dedb60b6208aafdfb2328a93543e3d94500978",
            image_hash="sha256:c1282f65b5c327db4dcc6cdfb27e91338bd625d119d9ae769318f089d82e35e2",
        ),
        CommitMetric(
            commit_timestamp=datetime.fromtimestamp(1619381788.0, tz=timezone.utc),
            namespace="basic-nginx-build",
            name="basic-nginx",
            commit_hash="15dedb60b6208aafdfb2328a93543e3d94500978",
            image_hash="sha256:4a20c8cfa48af3a938462e9cd7bfa0b16abfbc6ba16f0999f3931c79b1130e4b",
        ),
        CommitMetric(
            commit_timestamp=datetime.fromtimestamp(1620401174.0, tz=timezone.utc),
            namespace="basic-nginx-build",
            name="basic-nginx",
            commit_hash="620ce8b570c644338ba34224fc09b2d8a30bca02",
            image_hash="sha256:71309995e6da43b76079a649b00e0aa8378443e72f1fccc76af0d73d67a7f644",
        ),
    ]
    metrics.sort(key=lambda commit: commit.commit_timestamp)  # type: ignore
    return metrics


@pytest.mark.mockoon
def test_github_provider():
    collector = setup_collector_from_env_loading()

    actual = list(collector.generate_metrics())

    actual.sort(key=lambda commit: commit.commit_timestamp)

    assert actual == expected_commits()

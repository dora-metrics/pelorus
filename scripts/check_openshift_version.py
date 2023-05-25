#!/usr/bin/env python3

import json
import logging
from http.client import HTTPResponse
from pathlib import Path
from typing import Dict, List
from urllib import request
from urllib.error import HTTPError

import semver

ROOT = Path(__file__).resolve().parent.parent
FILES_IN_PELORUS = [
    ROOT / ".github/ISSUE_TEMPLATE/bug.yml",
    ROOT / "docs/UpstreamSupport.md",
]
FILES_IN_OPENSHIFT = [
    "ci-operator/jobs/dora-metrics/pelorus/dora-metrics-pelorus-master-presubmits.yaml",
    "ci-operator/jobs/dora-metrics/pelorus/dora-metrics-pelorus-master-periodics.yaml",
    "ci-operator/config/dora-metrics/pelorus/dora-metrics-pelorus-master__{version}.yaml",
]
OPENSHIFT_REPO = "openshift/release"
OPENSHIFT_BRANCH = "master"
RAW_URL = f"https://raw.githubusercontent.com/{OPENSHIFT_REPO}/{OPENSHIFT_BRANCH}"


def get_supported_versions() -> List[str]:
    with request.urlopen(
        "https://openshift-release.apps.ci.l2s4.p1.openshiftapps.com/graph"
    ) as response:
        versions: List[Dict[str, str]] = list(json.load(response)["nodes"])
    stable_versions = [
        version["version"]
        for version in versions
        if not version["version"].upper().isupper()
    ]
    minor_versions = {
        semver.VersionInfo.parse(version).replace(patch=0)
        for version in stable_versions
    }
    latest_minor_versions = list(minor_versions)
    latest_minor_versions.sort(reverse=True)

    return [f"{version.major}.{version.minor}" for version in latest_minor_versions[:4]]


def check_version_in_openshift_repo(version: str, file_name: str) -> None:
    response: HTTPResponse
    with request.urlopen(f"{RAW_URL}/{file_name}") as response:
        # TODO check if no old versions exist in file
        if version not in response.read().decode():
            logging.error(
                f"Missing version {version} in {file_name} in {OPENSHIFT_BRANCH} branch of {OPENSHIFT_REPO}"
            )


def check_versions(versions: List[str]) -> None:
    """
    Check if all supported OpenShift versions are being used/advertised.

    Parameters
    ----------
    versions : List[str]
        Currently supported OpenShift versions by the Pelorus project.

    """
    for file in FILES_IN_PELORUS:
        for version in versions:
            # TODO check if no old versions exist in file
            if version not in file.read_text():
                logging.error(f"Missing version {version} in {file}")
    for file in FILES_IN_OPENSHIFT:
        for version in versions:
            file_name = file.format(version=version)
            try:
                # TODO check if no old version file exist in folder
                check_version_in_openshift_repo(version=version, file_name=file_name)
            except HTTPError:
                logging.error(
                    f"File {file_name} does not exist in {OPENSHIFT_BRANCH} branch of {OPENSHIFT_REPO}"
                )


def main() -> None:
    check_versions(get_supported_versions())

    log_cache: dict = logging.getLogger()._cache
    if log_cache.get(logging.ERROR):
        raise SystemExit(1)
    logging.info("Everything is up to date")


# TODO create automated update command to update these files with the new
# versions and delete old ones
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

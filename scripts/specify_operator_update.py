#!/usr/bin/env python3
"""
Script to add replaces and skips sections to Pelorus Operator
ClusterServiceVersion file, located in

../pelorus-operator/bundle/manifests/pelorus-operator.clusterserviceversion.yaml

More info: https://olm.operatorframework.io/docs/concepts/olm-architecture/operator-catalog/creating-an-update-graph/
"""

import argparse
import sys
from pathlib import Path
from typing import List

YAML_TAB = "  "


def path_type(file_path: str) -> Path:
    _file_path = Path(file_path).resolve()
    if _file_path.exists():
        return _file_path
    raise argparse.ArgumentTypeError(f"Folder {_file_path} does not exist.")


def exit_error(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main(
    new_version: str, cluster_service_version_file: Path, versions: List[str]
) -> None:
    if new_version in versions:
        exit_error(f"version {new_version} already exists in Pelorus Operator tags.")

    with open(cluster_service_version_file, encoding="utf-8") as file_content:
        cluster_service_version_file_content = file_content.readlines()

    cluster_service_version_file_content.append(
        f"{YAML_TAB}replaces: pelorus-operator.v{versions[0]}\n"
    )
    cluster_service_version_file_content.append(f"{YAML_TAB}skips:\n")
    for version in versions:
        cluster_service_version_file_content.append(
            f"{YAML_TAB*2}- pelorus-operator.v{version}\n"
        )

    with open(cluster_service_version_file, mode="w", encoding="utf-8") as file_content:
        file_content.writelines(cluster_service_version_file_content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Updates ClusterServiceVersion of new Pelorus Operator."
    )
    parser.add_argument(
        "new_version", type=str, help="New version of Pelorus Operator."
    )
    parser.add_argument(
        "destination_path", type=path_type, help="Folder of Pelorus Operator."
    )
    parser.add_argument(
        "versions", nargs="*", help="Pelorus Operator versions, filtered and sorted."
    )

    cluster_service_version_file = (
        Path(parser.parse_args().destination_path).resolve()
        / "bundle/manifests/pelorus-operator.clusterserviceversion.yaml"
    )
    if not cluster_service_version_file.exists():
        exit_error(f"{cluster_service_version_file} does not exist.")

    main(
        parser.parse_args().new_version,
        cluster_service_version_file,
        parser.parse_args().versions,
    )

#!/usr/bin/env python3

import argparse
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import semver

from common import read_key, update_key
from update_projects_version import (
    PELORUS_CHARTS_FOLDER,
    PELORUS_EXPORTERS_FOLDER,
    PELORUS_OPERATOR_FOLDER,
    ROOT,
    VIRTUAL_ENVIRONMENT,
    check_prerequisites,
    run_command,
)

OPERATOR_NAME = "pelorus-operator"
OPERATOR_ORGANIZATION_NAME = "pelorus"
OPERATOR_DOMAIN = "pelorus.dora-metrics.io"

DIFF_FILE = ROOT / "current-to-next.diff"


def create_operator_sdk_structure(destination: Path) -> None:
    logging.info("Creating operator init files")
    run_command(
        f"operator-sdk init --plugins=helm --domain={OPERATOR_DOMAIN} --project-name={OPERATOR_NAME}",
        directory=destination,
    )
    logging.info("Creating operator api")
    exporters_charts_in_operator = destination / "helm-charts/pelorus/charts/exporters"
    exporters_charts_in_operator.mkdir(parents=True)
    shutil.copytree(
        PELORUS_EXPORTERS_FOLDER, exporters_charts_in_operator, dirs_exist_ok=True
    )
    run_command(
        f"operator-sdk create api --helm-chart={PELORUS_CHARTS_FOLDER}",
        directory=destination,
    )
    logging.info("Generating operator kustomize manifests files")
    run_command(
        "operator-sdk generate kustomize manifests -q --interactive=false",
        directory=destination,
    )


def get_next_operator_sdk_version(version: str) -> None:
    (VIRTUAL_ENVIRONMENT / "bin/operator-sdk").unlink()
    update_key("OPERATOR_SDK_VERSION", version)
    install_script = ROOT / "scripts/install_dev_tools.sh"
    run_command(f"{install_script} -c operator-sdk -v {VIRTUAL_ENVIRONMENT}")


def main(arguments: argparse.Namespace) -> None:
    check_prerequisites()
    current_operator_sdk_version = semver.VersionInfo.parse(
        read_key("OPERATOR_SDK_VERSION").lstrip("v")
    )
    next_operator_sdk_version = semver.VersionInfo.parse(arguments.version.lstrip("v"))
    if next_operator_sdk_version < current_operator_sdk_version:
        logging.error("Invalid version to update")
        raise SystemExit(1)

    with tempfile.TemporaryDirectory() as directory_name:
        temporary_directory = Path(directory_name)
        current_version_directory = temporary_directory / "current-version"
        current_version_directory.mkdir()
        next_version_directory = temporary_directory / "next-version"
        next_version_directory.mkdir()

        create_operator_sdk_structure(current_version_directory)

        get_next_operator_sdk_version(arguments.version)
        logging.info(run_command("operator-sdk version").stdout.strip())
        create_operator_sdk_structure(next_version_directory)

        # TODO check return code
        #   0 no diff - OK
        #   1 diffs - OK
        #   other - ERROR
        diff_content = subprocess.run(
            f"diff -ruN -x helm-charts {current_version_directory} {next_version_directory}",
            shell=True,
            check=False,  # returns 1 if there are differences
            capture_output=True,
            encoding="utf-8",
        ).stdout
        diff_content = diff_content.replace(current_version_directory.as_posix(), "")
        diff_content = diff_content.replace(next_version_directory.as_posix(), "")
        with DIFF_FILE.open("w", encoding="utf-8") as file:
            file.write(diff_content)

    # run_command(
    #     f"patch -p0 --verbose -i {DIFF_FILE}", directory=PELORUS_OPERATOR_FOLDER
    # )

    logging.info(f"{DIFF_FILE} file created successfully.")
    logging.info("After reviewing it, apply it running")
    logging.info(f"  patch -p1 --verbose -d {PELORUS_OPERATOR_FOLDER} -i {DIFF_FILE}")
    logging.info("Delete the file afterwards")
    logging.info(
        "Also, check if manual steps are needed in Operator SDK upgrading notes "
        "https://sdk.operatorframework.io/docs/upgrading-sdk-version/"
    )


def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        # TODO more information
        description="Update project's Operator SDK version.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "version",
        type=str,
        help="Version to update Operator SDK to. Example format 'v1.2.3'",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    main(arguments=get_arguments())

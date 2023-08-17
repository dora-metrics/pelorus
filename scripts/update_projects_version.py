#!/usr/bin/env python3
#
# Copyright Red Hat
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
"""
Script to update all versions of the project.

More info: https://pelorus.readthedocs.io/en/latest/Development/#versioning-process
"""

import argparse
import json
import logging
import re
import shutil
import subprocess
from http.client import HTTPResponse
from pathlib import Path
from typing import Dict, List, Optional
from urllib import request

import semver

OPERATOR_NAME = "pelorus-operator"
OPERATOR_ORGANIZATION_NAME = "pelorus"
OPERATOR_DOMAIN = "pelorus.dora-metrics.io"

ROOT = Path(__file__).resolve().parent.parent
PELORUS_CHARTS_FOLDER = ROOT / "charts/pelorus"
PELORUS_EXPORTERS_FOLDER = PELORUS_CHARTS_FOLDER / "charts/exporters"
PELORUS_OPERATOR_FOLDER = ROOT / "pelorus-operator"
PATCHES_FOLDER = ROOT / "scripts/pelorus-operator-patches"
VIRTUAL_ENVIRONMENT = ROOT / ".venv"

YAML_TAB = "  "
VERSION_PATTERN = r"\d+\.\d+\.\d+(-rc\.\d+)?"
SHELL_DEPENDENCIES = ["helm", "oc", "operator-sdk"]
MAJOR_LABEL = "major"
MINOR_LABEL = "minor"
PATCH_LABEL = "patch"
LABELS_OPTIONS = [MAJOR_LABEL, MINOR_LABEL, PATCH_LABEL]
CHARTS_FILES_TO_UPDATE = {
    # Files to updated in charts folder and number of changes in each one
    PELORUS_CHARTS_FOLDER / "Chart.yaml": 2,
    ROOT / "charts/operators/Chart.yaml": 1,
    PELORUS_EXPORTERS_FOLDER / "Chart.yaml": 1,
    PELORUS_EXPORTERS_FOLDER / "templates/_deploymentconfig.yaml": 1,
    PELORUS_EXPORTERS_FOLDER / "templates/_imagestream_from_image.yaml": 1,
}
DEVELOPMENT_FILE = ROOT / "docs/Development.md"

OPERATOR_RELEASED_TAGS_URL = (
    "https://quay.io/api/v1/repository/pelorus/pelorus-operator/tag/"
)
PELORUS_REPO_RAW_URL = (
    "https://raw.githubusercontent.com/dora-metrics/pelorus/master/{file_name}"
)

OPERATOR_CSV_FILE_NAME = "pelorus-operator.clusterserviceversion.yaml"
CHART_VERSION_FILE_NAME = "charts/pelorus/Chart.yaml"
OPERATOR_VERSION_FILE_NAME = (
    f"pelorus-operator/bundle/manifests/{OPERATOR_CSV_FILE_NAME}"
)


def exit_error(message: str) -> None:
    logging.error(message)
    raise SystemExit(1)


def folder_path_type(file_path: str) -> Path:
    _file_path = Path(file_path).resolve()
    if _file_path.exists():
        if _file_path.is_file():
            raise argparse.ArgumentTypeError("Must be a folder, not a file")
        return _file_path
    raise argparse.ArgumentTypeError(f"Path {_file_path} does not exist.")


def _to_dict(_list: List[str]) -> Dict[str, str]:
    return {"chart": _list[0], "operator": _list[1]}


def run_command(
    command: str, directory: Optional[Path] = None, error_message: Optional[str] = None
) -> "subprocess.CompletedProcess[str]":
    try:
        return subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            encoding="utf-8",
            cwd=directory,
        )
    except subprocess.CalledProcessError as error:
        if error_message:
            logging.error(error_message)
        else:
            logging.error(str(error.stderr).strip())
            logging.error(error)
        raise SystemExit(error.returncode) from error


def check_prerequisites(destination: Path, force: bool) -> None:
    if not PATCHES_FOLDER.exists():
        exit_error(f"Patches folder {PATCHES_FOLDER} does not exist")

    if force:
        logging.info(f"Removing destination folder {destination}")
        shutil.rmtree(destination)
        destination.mkdir(parents=True)

    if any(destination.iterdir()):
        exit_error(f"Destination folder {destination} is not empty")

    for dependency in SHELL_DEPENDENCIES:
        dependency_path = shutil.which(dependency)
        if dependency_path is None:
            exit_error(
                f"{dependency} executable not found, activate the project's virtual environment {VIRTUAL_ENVIRONMENT}"
            )
        if str(VIRTUAL_ENVIRONMENT) not in dependency_path:
            logging.warning(
                f"Activate the project's virtual environment {VIRTUAL_ENVIRONMENT} to use latest "
                "versions of the shell dependencies"
            )

    run_command(
        "oc auth can-i '*' '*' --all-namespaces",
        error_message=(
            "You must be logged in to a OpenShift cluster as a user with cluster-admin "
            "permissions to run this script. This avoids RBAC problems. More info: "
            "https://sdk.operatorframework.io/docs/building-operators/helm/tutorial/#prerequisites"
        ),
    )
    run_command(
        "oc get crd grafanas.integreatly.org",
        error_message="Grafana CRD not found",
    )
    run_command(
        "oc get crd prometheuses.monitoring.coreos.com",
        error_message="Prometheus CRD not found",
    )

    logging.info(run_command("operator-sdk version").stdout.strip())


def get_version_upstream(file_name: str) -> semver.VersionInfo:
    current_version = None

    response: HTTPResponse
    with request.urlopen(PELORUS_REPO_RAW_URL.format(file_name=file_name)) as response:
        match = re.search(VERSION_PATTERN, response.read().decode())
        if match:
            current_version = semver.VersionInfo.parse(match.group())
    if current_version is None:
        exit_error(f"Version was not found in {file_name} in master branch")
    return current_version


def bump_version(
    version: semver.VersionInfo, software: str, arguments: argparse.Namespace
) -> semver.VersionInfo:
    # TODO move this to chart-check?
    if version.build is not None:
        raise ValueError

    if arguments.labels[software] == MAJOR_LABEL:
        return version.bump_major()
    if arguments.labels[software] == MINOR_LABEL:
        return version.bump_minor()
    if arguments.labels[software] == PATCH_LABEL:
        return version.next_version("patch")
    if arguments.pre_release:
        if version.prerelease:
            return version.bump_prerelease()
        return version.next_version("patch").bump_prerelease()


def get_next_version(
    file_name: str, software: str, arguments: argparse.Namespace
) -> str:
    current_version = get_version_upstream(file_name=file_name)
    logging.info(f"Current {software} version (upstream): {current_version}")
    next_version = bump_version(current_version, software=software, arguments=arguments)
    logging.info(f"Bumping {software} version to {next_version}")

    return str(next_version)


def replace_in_file(file: Path, pattern: str, new: str, number_of_changes: int) -> None:
    current_content = file.read_text()
    match = re.search(pattern, current_content)
    if match:
        file.write_text(current_content.replace(match.group(), new))
    else:
        exit_error(f"Pattern {pattern} was not found in {file}")
    # Verification if the changes were actually applied
    if file.read_text().count(new) != number_of_changes:
        exit_error(f"Unexpected changes in {file}")


def update_charts_folder(next_chart_version: str) -> None:
    for file, occurrences in CHARTS_FILES_TO_UPDATE.items():
        replace_in_file(
            file=file,
            pattern=VERSION_PATTERN,
            new=next_chart_version,
            number_of_changes=occurrences,
        )

    run_command(f"helm dep update {PELORUS_CHARTS_FOLDER}")
    tar_files = (PELORUS_CHARTS_FOLDER / "charts").glob("*.tgz")
    for file in tar_files:
        file.unlink()


def add_replaces_to_csv(
    new_version: str, cluster_service_version_file: Path, versions: List[str]
) -> None:
    if not cluster_service_version_file.exists():
        exit_error(f"{cluster_service_version_file} does not exist.")
    if new_version in versions:
        # TODO move this to chart-check?
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


def update_operator_folder(next_operator_version: str, destination: Path) -> None:
    logging.info("Creating operator init files")
    # TODO run update command instead of init every time
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
    for file in exporters_charts_in_operator.parent.glob("*.tgz"):
        file.unlink()

    replace_in_file(
        file=PELORUS_OPERATOR_FOLDER / "Makefile",
        pattern=r"VERSION \?= 0\.0\.1",
        new=f"VERSION ?= {next_operator_version}",
        number_of_changes=1,
    )
    operator_image = f"quay.io/{OPERATOR_ORGANIZATION_NAME}/{OPERATOR_NAME}"
    replace_in_file(
        file=PELORUS_OPERATOR_FOLDER / "Makefile",
        pattern=r"IMAGE_TAG_BASE \?= pelorus\.dora-metrics\.io/pelorus-operator",
        new=f"IMAGE_TAG_BASE ?= {operator_image}",
        number_of_changes=1,
    )
    logging.info("Generating operator kustomize manifests files")
    run_command(
        "operator-sdk generate kustomize manifests -q --interactive=false",
        directory=destination,
    )

    for file in PATCHES_FOLDER.rglob("*"):
        if file.is_file():
            logging.info(f"Applying patch {file}")
            run_command(f"patch -d {destination} -p0 < {file}")

    replace_in_file(
        file=PELORUS_OPERATOR_FOLDER
        / f"config/manifests/bases/{OPERATOR_CSV_FILE_NAME}",
        pattern="    containerImage: placeholder",
        new=f"    containerImage: {operator_image}:{next_operator_version}",
        number_of_changes=1,
    )
    logging.info("Executing operator make bundle")
    run_command("make bundle", directory=destination)

    pelorus_operator_image_tags = request.Request(OPERATOR_RELEASED_TAGS_URL)
    pelorus_operator_image_tags.add_header("Authorization", "Bearer XYZ")
    with request.urlopen(pelorus_operator_image_tags) as response:
        tags: List[Dict[str, str]] = list(json.load(response)["tags"])
    tag_names = [
        tag["name"]
        for tag in tags
        if tag.get("end_ts") is None and not tag["name"].upper().isupper()
    ]
    tag_names.sort(reverse=True, key=lambda version: semver.VersionInfo.parse(version))

    add_replaces_to_csv(
        new_version=next_operator_version,
        cluster_service_version_file=destination
        / f"bundle/manifests/{OPERATOR_CSV_FILE_NAME}",
        versions=tag_names,
    )

    logging.info(f"Updated operator available at {destination}")


def main(arguments: argparse.Namespace) -> None:
    arguments.labels = _to_dict(arguments.labels)

    check_prerequisites(destination=arguments.destination, force=arguments.force)

    next_chart_version = get_next_version(
        file_name=CHART_VERSION_FILE_NAME,
        software="chart",
        arguments=arguments,
    )
    update_charts_folder(
        next_chart_version=next_chart_version,
    )

    next_operator_version = get_next_version(
        file_name=OPERATOR_VERSION_FILE_NAME,
        software="operator",
        arguments=arguments,
    )
    update_operator_folder(
        next_operator_version=next_operator_version,
        destination=arguments.destination,
    )

    if arguments.labels["chart"] == MAJOR_LABEL:
        logging.info('IMPORTANT: label your PR with "major"')
    if arguments.labels["chart"] == MINOR_LABEL:
        logging.info('IMPORTANT: label your PR with "minor"')
    if not arguments.pre_release:
        replace_in_file(
            file=DEVELOPMENT_FILE,
            pattern=VERSION_PATTERN,
            new=next_chart_version,
            number_of_changes=2,
        )
        logging.info("IMPORTANT: this change will result in a new release")
    logging.info("Update finished successfully")


def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update all versions of the project.",
        allow_abbrev=False,
    )
    folder = parser.add_mutually_exclusive_group()
    folder.add_argument(
        "-d",
        "--destination",
        type=folder_path_type,
        help=f"Path to operator destination folder. Default to {PELORUS_OPERATOR_FOLDER}",
        default=PELORUS_OPERATOR_FOLDER,
    )
    folder.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Removes destination folder before proceeding.",
    )
    labels = parser.add_mutually_exclusive_group(required=True)
    labels.add_argument(
        "-l",
        "--labels",
        nargs=2,
        choices=LABELS_OPTIONS,
        default=[None, None],
        help="Update strategy to Chart and Operator, respectively.",
    )
    labels.add_argument(
        "-r",
        "--pre-release",
        action="store_true",
        help="Pre release update to all project versions.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    main(arguments=get_arguments())

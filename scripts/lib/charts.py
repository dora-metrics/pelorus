"""Functions related to linting and modifying helm charts"""

import re
import subprocess
from pathlib import Path
from typing import Tuple, Union

import semver
import yaml


def chart_yaml_path(chart_path: Path) -> Path:
    """
    Resolve the path to the Chart.yaml file,
    whether it is given or just the directory containing it.
    """
    if chart_path.is_dir():
        return chart_path / "Chart.yaml"
    else:
        return chart_path


def get_next_patch(chart_path: Path) -> semver.VersionInfo:
    "Get the next semver patch number in the given Chart."
    with chart_yaml_path(chart_path).open() as chart_file:
        chart = yaml.load(chart_file, Loader=yaml.FullLoader)
        version = semver.VersionInfo.parse(chart["version"])

        return version.bump_patch()


def bump_with_version(chart_path: Path, version: Union[semver.VersionInfo, str]):
    "Bump the given Chart to the given Version."
    version = str(version)

    with chart_yaml_path(chart_path).open("r+") as chart_file:
        lines = chart_file.readlines()
        for i, line in enumerate(lines):
            if "version:" not in line:
                continue

            lines[i] = f"version: {version}\n"
            break

        # linter will complain about trailing newlines
        lines[-1] = lines[-1].rstrip()
        # readlines will have moved us somewhere in the file-- go back to the beginning for writing.
        chart_file.seek(0)
        chart_file.writelines(lines)


def bump(chart_path: Path):
    """Bump the given Chart to the next patch version."""
    next_patch = get_next_patch(chart_path)
    print(f"🚢 🆙 Bumping {chart_path} to {next_patch}")
    bump_with_version(chart_path, next_patch)


CHART_VERSION_NOT_OKAY_REGEX = re.compile(
    r'^.*path: "(.*)".*Chart version.*$', re.MULTILINE
)


def run_chart_lint() -> Tuple[int, list[str]]:
    "Lint charts against upstream, returning the return code and the list of charts that have bad versions"
    CMD = "ct lint --remote upstream"
    print("🚢 Linting helm charts")
    print(CMD)
    lint_result = subprocess.run(
        CMD.split(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    print(lint_result.stdout)
    print()

    if lint_result.returncode != 0:
        charts = CHART_VERSION_NOT_OKAY_REGEX.findall(lint_result.stdout)
    else:
        charts = []

    return lint_result.returncode, charts


def check_and_bump_all() -> int:
    """
    Check all charts, continuously bumping any that have bad versions.
    Returns the last exit status of the linter after versions have been bumped.
    """
    changed_charts = set()
    last_code, failed_charts = run_chart_lint()
    while failed_charts:
        for chart in failed_charts:
            bump(Path(chart))
            changed_charts.add(chart)

        print("🚢 Linting helm charts again")
        last_code, failed_charts = run_chart_lint()
        if failed_charts:
            print(
                "🚢 🔁 Bumping versions again. If this keeps happening, cancel with Ctrl-C and investigate further."
            )
    return last_code

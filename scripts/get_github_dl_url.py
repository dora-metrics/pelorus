#!/usr/bin/env python3
import argparse
import enum
import platform
import re
import sys
from typing import Callable, Iterable, NamedTuple

import requests

GITHUB_RELEASE_TEMPLATE = "https://api.github.com/repos/{}/releases/latest"

OS = platform.system()
ARCH = platform.machine()

X86_64_ARCH_NAMES = {"x86_64", "arm64"}


class StandardTool:
    TAR_GZ_PATTERN = re.compile(r"https://.*\.tar\.gz")
    KERNEL_PATTERN = re.compile(OS, re.IGNORECASE)

    if OS == "Darwin":
        # some projects ship "universal binaries" which support x86 and ARM.
        # they usually use "all" in the "arch" portion.
        if ARCH in X86_64_ARCH_NAMES:
            ARCH_PATTERN = re.compile("all|" + "|".join(X86_64_ARCH_NAMES))
        elif ARCH == "arm64":
            ARCH_PATTERN = re.compile("all|arm64")
        else:
            sys.exit(f"Unsupported architecture {ARCH}")
    elif OS == "Linux":
        if ARCH in X86_64_ARCH_NAMES:
            ARCH_PATTERN = re.compile("|".join(X86_64_ARCH_NAMES))
        else:
            sys.exit(f"Unsupported architecture {ARCH}")
    else:
        sys.exit(f"Unsupported OS {OS}")

    PATTERNS = TAR_GZ_PATTERN, KERNEL_PATTERN, ARCH_PATTERN

    @classmethod
    def url_matches(cls, url: str) -> bool:
        return all(pat.search(url) for pat in cls.PATTERNS)


class Nooba:
    repo = "noobaa/noobaa-operator"
    arch = "mac" if ARCH == "Darwin" else ARCH
    pattern = re.compile(f"https://(.*)-{arch}-(.*)[0-9]")

    @classmethod
    def url_matches(cls, url: str) -> bool:
        return cls.pattern.search(url) is not None


class OperatorSdk:
    repo = "operator-framework/operator-sdk"

    if ARCH in X86_64_ARCH_NAMES:
        arch = "amd64"
    else:
        arch = ARCH

    pattern = re.compile(f"operator-sdk_{OS.lower()}_{arch}")

    @classmethod
    def url_matches(cls, url: str) -> bool:
        return cls.pattern.search(url) is not None


class Tool(enum.Enum):
    def __init__(self, repo: str, matcher: Callable[[str], bool]):
        self.repo = repo
        self.matcher = matcher

    TEKTON = "tektoncd/cli", StandardTool.url_matches
    CHART_TEST = "helm/chart-testing", StandardTool.url_matches
    CONFTEST = "open-policy-agent/conftest", StandardTool.url_matches
    PROMETHEUS = "prometheus/prometheus", StandardTool.url_matches

    NOOBA = Nooba.repo, Nooba.url_matches

    OPERATOR_SDK = OperatorSdk.repo, OperatorSdk.url_matches


class ExecutableToTool(enum.Enum):
    """
    Maps an executable name to a tool.
    """

    def __init__(self, tool: Tool):
        self.tool = tool

    tkn = (Tool.TEKTON,)
    ct = (Tool.CHART_TEST,)
    promtool = (Tool.PROMETHEUS,)
    conftest = (Tool.CONFTEST,)
    noobaa = (Tool.NOOBA,)
    operator_sdk = (Tool.OPERATOR_SDK,)


class ReleaseAsset(NamedTuple):
    name: str
    url: str
    """
    The download url, not the release or asset URL.
    """

    @classmethod
    def from_json(cls, asset_dict: dict):
        name = asset_dict["name"]
        url = asset_dict["browser_download_url"]
        return cls(name, url)


def get_latest_assets(repo: str) -> Iterable[ReleaseAsset]:
    url = GITHUB_RELEASE_TEMPLATE.format(repo)

    response = requests.get(url)
    response.raise_for_status()

    body = response.json()

    for asset in body["assets"]:
        yield ReleaseAsset.from_json(asset)


parser = argparse.ArgumentParser(
    description="Extract the download URL for software hosted on github, taking into account OS and Architecture."
)
parser.add_argument(
    "software",
    metavar="executable",
    type=str,
    help="The executable to retrieve the URL for.",
    choices={name.replace("_", "-") for name in ExecutableToTool._member_names_},
)

if __name__ == "__main__":
    args = parser.parse_args()
    software: str = args.software.replace("-", "_")

    tool = ExecutableToTool[software].tool

    for asset in get_latest_assets(tool.repo):
        if tool.matcher(asset.url):
            print(asset.url)
            sys.exit()

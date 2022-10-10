#!/usr/bin/env python3
"""
Extract the download URL for software hosted on github, taking into account OS and Architecture.
"""
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

X86_64_ARCH_NAMES = {"x86_64", "amd64"}

# TOOLS:
# these are ways to test the URLs of each release asset
# to match our operating system and architecture.
# the special exceptions have their repo name also, for convenience.


class StandardTool:
    "The URL pattern for most tools we use."

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
    "Nooba's URL pattern."

    repo = "noobaa/noobaa-operator"
    arch = "mac" if OS == "Darwin" else "linux"
    pattern = re.compile(f"https://(.*)-{arch}-(.*)[0-9]")

    @classmethod
    def url_matches(cls, url: str) -> bool:
        return cls.pattern.search(url) is not None


class OperatorSdk:
    "The operator SDK's URL pattern."

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
    "Maps the dev tools we want to their repos and respective URL matchers."

    def __init__(self, repo: str, matcher: Callable[[str], bool]):
        self.repo = repo
        self.matcher = matcher

    tkn = "tektoncd/cli", StandardTool.url_matches
    ct = "helm/chart-testing", StandardTool.url_matches
    conftest = "open-policy-agent/conftest", StandardTool.url_matches
    promtool = "prometheus/prometheus", StandardTool.url_matches

    noobaa = Nooba.repo, Nooba.url_matches

    operator_sdk = OperatorSdk.repo, OperatorSdk.url_matches


class ReleaseAsset(NamedTuple):
    "A file attached to a github release."

    name: str
    "The name of the file (for debug purposes)"

    url: str
    "The download url, not the release or asset URL."

    @classmethod
    def from_json(cls, asset_dict: dict):
        name = asset_dict["name"]
        url = asset_dict["browser_download_url"]
        return cls(name, url)


def get_latest_assets(repo: str) -> Iterable[ReleaseAsset]:
    "Get the release assets for the latest release."
    url = GITHUB_RELEASE_TEMPLATE.format(repo)

    response = requests.get(url)
    response.raise_for_status()

    body = response.json()

    for asset in body["assets"]:
        yield ReleaseAsset.from_json(asset)


CLI_NAMES = {name.replace("_", "-") for name in Tool._member_names_}

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "software",
    metavar="executable",
    type=str,
    help=f"The executable to retrieve the URL for.\nSupported: {', '.join(CLI_NAMES)}",
    choices=CLI_NAMES,
)

if __name__ == "__main__":
    args = parser.parse_args()
    software: str = args.software.replace("-", "_")

    tool = Tool[software]

    for asset in get_latest_assets(tool.repo):
        if tool.matcher(asset.url):
            print(asset.url)
            sys.exit()

    sys.exit(f"No matching download URL found for {software} on {OS} {ARCH}")

#!/usr/bin/env python3
"""
Extract the download URL for software hosted on github, taking into account OS and Architecture.
"""
import argparse
import enum
import platform
import re
import sys
from typing import Callable, Iterable, Literal, NamedTuple, cast

import requests
import semver

GITHUB_RELEASE_TEMPLATE = "https://api.github.com/repos/{}/releases"


SUPPORTED_SYSTEMS = {"Linux", "Darwin"}

_os = platform.system()
if _os not in SUPPORTED_SYSTEMS:
    sys.exit(f"Unsupported OS {_os}")

OS = cast(Literal["Linux", "Darwin"], _os)

X86_64_ARCH_NAMES = {"x86_64", "amd64"}
SUPPORTED_ARCHES = X86_64_ARCH_NAMES | {"arm64"}

_arch = platform.machine()
if _arch not in SUPPORTED_ARCHES:
    sys.exit(f"Unsupported architecture {_arch}")

ARCH = cast(Literal["x86_64", "arm64", "amd64"], _arch)


# TOOLS:
# these are ways to test the URLs of each release asset
# to match our operating system and architecture.
# the special exceptions have their repo name also, for convenience.


class StandardTool:
    "The URL pattern for most tools we use."

    TAR_GZ_PATTERN = re.compile(r"https://.*\.tar\.[gx]z")
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
    elif OS == "Linux" and ARCH in X86_64_ARCH_NAMES:
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
    shellcheck = "koalaman/shellcheck", StandardTool.url_matches

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


def oc_url():
    "Get the URL to download the OpenShift client (`oc`)"
    if OS == "Darwin":
        # there's currently a bug with how go handles certificates on macOS (https://github.com/golang/go/issues/52010),
        # and thus affects `oc`` >= 4.11 (https://bugzilla.redhat.com/show_bug.cgi?id=2097830).
        # The workaround is to install a 4.10 client.
        version = "4.10.40"

        if ARCH == "arm64":
            filename_suffix = "mac-arm64"
        else:
            filename_suffix = "mac"
    else:
        filename_suffix = "linux"
        version = "stable"

    # I can't say for sure why arm64 bins are available under x86_64, but this isn't a typo.
    BASE_URL = "https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp"
    return f"{BASE_URL}/{version}/openshift-client-{filename_suffix}.tar.gz"


def get_latest_assets(repo: str, exact: str = "") -> Iterable[ReleaseAsset]:
    "Get the release assets for the latest release, if no exact version."
    url = GITHUB_RELEASE_TEMPLATE.format(repo)

    response = requests.get(url)
    response.raise_for_status()

    body = response.json()

    highest_version = semver.VersionInfo(0, 0, 0)
    latest_release = None

    for release in body:
        version_string = release["tag_name"]
        if exact and exact == version_string:
            latest_release = release
            break
        if version_string.startswith("v"):
            version_string = version_string[1:]
        if version_string.endswith("+stringlabels"):
            # Special case for Prometheus, where there are
            # two different releases. We are interested in the
            # one without stringlabels:
            # https://prometheus.io/blog/2023/03/21/stringlabel/
            continue
        if semver.VersionInfo.is_valid(version_string):
            version = semver.VersionInfo.parse(version_string)
            if version > highest_version:
                highest_version = version
                latest_release = release

    if latest_release:
        for asset in latest_release["assets"]:
            yield ReleaseAsset.from_json(asset)


CLI_NAMES = {name.replace("_", "-") for name in Tool._member_names_} | {"oc"}

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

    if software == "oc":
        print(oc_url())
        sys.exit()

    exact = None
    if software == "ct":
        exact = "v3.8.0"  # https://github.com/helm/chart-testing/issues/577

    tool = Tool[software]

    for asset in get_latest_assets(tool.repo, exact):
        if tool.matcher(asset.url):
            print(asset.url)
            sys.exit()

    sys.exit(f"No matching download URL found for {software} on {OS} {ARCH}")

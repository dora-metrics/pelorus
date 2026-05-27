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

from __future__ import annotations

import functools
import logging
import re
from typing import Optional

import giturlparse
from attrs import define, field

from pelorus.utils import collect_bad_attribute_path_error, get_nested

__all__ = ["CommitMetric", "commit_metric_from_build", "sanitize_url", "SUPPORTED_PROTOCOLS"]

SUPPORTED_PROTOCOLS = {"http", "https", "ssh", "git"}

_URL_USERINFO_RE = re.compile(r"(https?://)([^@]+)@")


def sanitize_url(url: str) -> str:
    """Strip embedded credentials (user:pass@) from a URL for safe logging."""
    if not url:
        return url
    return _URL_USERINFO_RE.sub(r"\1", url)


# Pre-compiled regexes for Azure DevOps repo URL parsing
_AZURE_HTTP_RE = re.compile(
    r"^(?P<protocol>https?)\://"
    r"((?P<user>[a-zA-Z0-9_-]+)@)?"
    r"(?P<resource>[a-z0-9_.-]*)"
    r"[:/]*"
    r"(?P<port>[\d]+){0,1}"
    r"(?P<pathname>\/"
    r"(?P<owner>[\w\-\.]+)\/"
    r"(?P<azure_project>[\w\-\.]+)\/\_git\/"
    r"(?P<name>[\w\-\.]+)\/?)$"
)
_AZURE_SSH_RE = re.compile(
    r"^git@(?P<resource>"
    r"(?P<protocol>\w+)\.[a-z0-9_.-]*\:v3)"
    r"[:/]*"
    r"(?P<port>[\d]+){0,1}"
    r"(?P<pathname>\/"
    r"(?P<owner>[\w\-\.]+)\/"
    r"(?P<azure_project>[\w\-\.]+)\/"
    r"(?P<name>[\w\-\.]+)\/?)$"
)

@functools.lru_cache(maxsize=256)
def _parse_repo_url_cached(url: str) -> tuple:
    """Parse a git repo URL into (protocol, fqdn, group, name, name, port, azure_project).

    Note: name and project are both set to parsed.name (repo name).
    """
    azure_project = None
    match = _AZURE_HTTP_RE.search(url)
    match_ssh = _AZURE_SSH_RE.search(url)
    if match_ssh:
        match = match_ssh
    if match:
        regex_group = match.groupdict()
        azure_project = regex_group.pop("azure_project")
        pre_parsed = {
            "protocols": [regex_group.get("protocol", "ssh")],
            "href": url,
            "user": None,
            "owner": None,
        }
        pre_parsed.update(regex_group)
        parsed = giturlparse.parser.Parsed(**pre_parsed)
    else:
        parsed = giturlparse.parse(url)
    if parsed.protocols and parsed.protocols[0] not in SUPPORTED_PROTOCOLS:
        raise ValueError(f"Unsupported protocol: {parsed.protocols[0]}")
    protocol = parsed.protocol
    fqdn = parsed.resource
    if parsed.pathname.startswith("//"):
        parts = parsed.pathname.split("/")
        fqdn = parts[2] if len(parts) > 2 and parts[2] else fqdn
        if parsed.protocols:
            protocol = parsed.protocols[0]
    return (protocol, fqdn, parsed.owner, parsed.name, parsed.name, parsed.port, azure_project)


@define
class CommitMetric:
    name: str = field()
    annotations: dict = field(factory=dict, kw_only=True)
    labels: dict = field(factory=dict, kw_only=True)
    namespace: Optional[str] = field(default=None, kw_only=True)

    __repo_url: Optional[str] = field(default=None, init=False)
    __repo_protocol: Optional[str] = field(default=None, init=False)
    __repo_fqdn: Optional[str] = field(default=None, init=False)
    __repo_group: Optional[str] = field(default=None, init=False)
    __repo_name: Optional[str] = field(default=None, init=False)
    __repo_project: Optional[str] = field(default=None, init=False)
    __repo_port: Optional[str] = field(default=None, init=False)
    __azure_project: Optional[str] = field(default=None, init=False)

    committer: Optional[str] = field(default=None, kw_only=True, repr=False)
    commit_hash: Optional[str] = field(default=None, kw_only=True)
    commit_time: Optional[str] = field(default=None, kw_only=True)
    """A human-readable timestamp."""
    commit_timestamp: Optional[float] = field(default=None, kw_only=True)
    """The unix timestamp."""
    commit_link: Optional[str] = field(default=None, kw_only=True)

    build_name: Optional[str] = field(default=None, kw_only=True)
    build_config_name: Optional[str] = field(default=None, kw_only=True)

    image_location: Optional[str] = field(default=None, kw_only=True)
    image_name: Optional[str] = field(default=None, kw_only=True)
    image_tag: Optional[str] = field(default=None, kw_only=True)
    image_hash: Optional[str] = field(default=None, kw_only=True)

    @property
    def repo_url(self):
        """
        The full URL for the repo, obtained from build metadata, Image annotations, etc.

        Setting this parses the URL and populates: repo_protocol, git_fqdn,
        repo_group, repo_name, repo_project, and azure_project.
        """
        return self.__repo_url

    @repo_url.setter
    def repo_url(self, value):
        # Ensure git URI does not end with "/", issue #590
        value = value.strip("/")
        self.__repo_url = value
        self.__parse_repourl()

    @property
    def repo_protocol(self):
        return self.__repo_protocol

    @property
    def git_fqdn(self):
        return self.__repo_fqdn

    @property
    def repo_group(self):
        return self.__repo_group

    @property
    def repo_name(self):
        return self.__repo_name

    @property
    def repo_project(self):
        return self.__repo_project

    @property
    def git_server(self):
        url = f"{self.__repo_protocol}://{self.__repo_fqdn}"

        if self.__repo_port:
            url += f":{self.__repo_port}"

        return url

    @property
    def azure_project(self):
        return self.__azure_project

    def __parse_repourl(self):
        logging.debug("repo url = %s", sanitize_url(self.__repo_url or ""))
        if self.__repo_url is None:
            return
        result = _parse_repo_url_cached(self.__repo_url)
        (self.__repo_protocol, self.__repo_fqdn, self.__repo_group,
         self.__repo_name, self.__repo_project, self.__repo_port,
         self.__azure_project) = result

    # Maps attribute names to (Build path, required). False = fallback handled elsewhere.
    _BUILD_MAPPING = dict(
        build_name=("metadata.name", True),
        build_config_name=("metadata.labels.buildconfig", True),
        namespace=("metadata.namespace", True),
        image_location=("status.outputDockerImageReference", True),
        image_hash=("status.output.to.imageDigest", True),
        commit_hash=("spec.revision.git.commit", False),
        repo_url=("spec.source.git.uri", False),
    )

    _ANNOTATION_MAPPING = dict(
        repo_url="io.openshift.build.source-location",
        commit_hash="io.openshift.build.commit.id",
        commit_time="io.openshift.build.commit.date",
    )


def commit_metric_from_build(app: str, build, errors: list) -> CommitMetric:
    """
    Create a CommitMetric from build information.
    Will collect errors for missing data instead of failing early.
    """
    metric = CommitMetric(app)
    for attr_name, (path, required) in CommitMetric._BUILD_MAPPING.items():
        with collect_bad_attribute_path_error(errors, required):
            value = get_nested(build, path, name="build")
            setattr(metric, attr_name, value)

    return metric

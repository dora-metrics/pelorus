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

import logging
import re
from typing import NamedTuple, Optional

import attrs
import giturlparse

from pelorus.utils import collect_bad_attribute_path_error, get_nested

DEFAULT_PROVIDER = "git"
PROVIDER_TYPES = {"git", "image"}
GIT_PROVIDER_TYPES = {"github", "bitbucket", "gitea", "azure-devops", "gitlab"}

SUPPORTED_PROTOCOLS = {"http", "https", "ssh", "git"}


# TODO: the majority of these fields are unused.
# Let's figure out why they're there.
@attrs.define
class CommitMetric:
    name: str = attrs.field()
    annotations: dict = attrs.field(default=None, kw_only=True)
    labels: dict = attrs.field(default=None, kw_only=True)
    namespace: Optional[str] = attrs.field(default=None, kw_only=True)

    __repo_url: str = attrs.field(default=None, init=False)
    __repo_protocol = attrs.field(default=None, init=False)
    __repo_fqdn: str = attrs.field(default=None, init=False)
    __repo_group = attrs.field(default=None, init=False)
    __repo_name = attrs.field(default=None, init=False)
    __repo_project = attrs.field(default=None, init=False)
    __repo_port = attrs.field(default=None, init=False)
    __azure_project = attrs.field(default=None, init=False)

    committer: Optional[str] = attrs.field(default=None, kw_only=True)
    commit_hash: Optional[str] = attrs.field(default=None, kw_only=True)
    commit_time: Optional[str] = attrs.field(default=None, kw_only=True)
    """
    A human-readable timestamp.
    In the future, this and commit_timestamp should be combined.
    """
    commit_timestamp: Optional[float] = attrs.field(default=None, kw_only=True)
    """
    The unix timestamp.
    In the future, this and commit_time should be combined.
    """

    build_name: Optional[str] = attrs.field(default=None, kw_only=True)
    build_config_name: Optional[str] = attrs.field(default=None, kw_only=True)

    image_location: Optional[str] = attrs.field(default=None, kw_only=True)
    image_name: Optional[str] = attrs.field(default=None, kw_only=True)
    image_tag: Optional[str] = attrs.field(default=None, kw_only=True)
    image_hash: Optional[str] = attrs.field(default=None, kw_only=True)

    @property
    def repo_url(self):
        """
        The full URL for the repo, obtained from build metadata, Image annotations, etc.

        Setting this will parse it and enable using the following fields:

        repo_{protocol,group,name,project}

        git_{server,fqdn}
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
        """Returns the Git server protocol"""
        return self.__repo_protocol

    @property
    def git_fqdn(self):
        """Returns the Git server FQDN"""
        return self.__repo_fqdn

    @property
    def repo_group(self):
        return self.__repo_group

    @property
    def repo_name(self):
        """Returns the Git repo name, example: myrepo.git"""
        return self.__repo_name

    @property
    def repo_project(self):
        """Returns the Git project name, this is normally the repo_name with '.git' parsed off the end."""
        return self.__repo_project

    @property
    def git_server(self):
        """Returns the Git server FQDN with the protocol"""
        url = f"{self.__repo_protocol}://{self.__repo_fqdn}"

        if self.__repo_port:
            url += f":{self.__repo_port}"

        return url

    @property
    def azure_project(self):
        return self.__azure_project

    def __parse_repourl(self):
        """Parse the repo_url into individual pieces"""
        logging.debug("repo url = %s", self.__repo_url)
        if self.__repo_url is None:
            return
        # http://user@dev.azure.com:8080/organization/project/_git/repository/
        regex = re.compile(
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
        match = regex.search(self.__repo_url)
        # git@ssh.dev.azure.com:v3/organization/project/repository/
        regex_ssh = re.compile(
            r"^git@(?P<resource>"
            r"(?P<protocol>\w+)\.[a-z0-9_.-]*\:v3)"
            r"[:/]*"
            r"(?P<port>[\d]+){0,1}"
            r"(?P<pathname>\/"
            r"(?P<owner>[\w\-\.]+)\/"
            r"(?P<azure_project>[\w\-\.]+)\/"
            r"(?P<name>[\w\-\.]+)\/?)$"
        )
        match_ssh = regex_ssh.search(self.__repo_url)
        if match_ssh:
            match = match_ssh
        if match:
            regex_group = match.groupdict()
            self.__azure_project = regex_group.pop("azure_project")
            pre_parsed = {
                "protocols": giturlparse.parse(self.__repo_url).protocols or ["ssh"],
                "href": self.__repo_url,
                "user": None,
                "owner": None,
            }
            pre_parsed.update(regex_group)
            parsed = giturlparse.parser.Parsed(**pre_parsed)
        else:
            parsed = giturlparse.parse(self.__repo_url)
        logging.debug("Parsed: %s", parsed)
        if len(parsed.protocols) > 0 and parsed.protocols[0] not in SUPPORTED_PROTOCOLS:
            raise ValueError("Unsupported protocol %s", parsed.protocols[0])
        self.__repo_protocol = parsed.protocol
        # In the case of multiple subgroups the host will be in the pathname
        # Otherwise, it will be in the resource
        if parsed.pathname.startswith("//"):
            self.__repo_fqdn = parsed.pathname.split("/")[2]
            self.__repo_protocol = parsed.protocols[0]
        else:
            self.__repo_fqdn = parsed.resource
        self.__repo_group = parsed.owner
        self.__repo_name = parsed.name
        self.__repo_project = parsed.name
        self.__repo_port = parsed.port

    # maps attributes to their location in a `Build`.
    #
    # missing attributes or with False argument are handled specially:
    #
    # name: set when the object is constructed
    # labels: must be converted from an `openshift.dynamic.ResourceField`
    # repo_url: if it's not present in the Build, fallback logic needs to be handled elsewhere
    # commit_hash: if it's missing in the Build, fallback logic needs to be handled elsewhere
    # commit_timestamp: very special handling, the main purpose of each committime collector
    # comitter: not required to calculate committime
    _BUILD_MAPPING = dict(
        build_name=("metadata.name", True),
        build_config_name=("metadata.labels.buildconfig", True),
        namespace=("metadata.namespace", True),
        image_location=("status.outputDockerImageReference", True),
        image_hash=("status.output.to.imageDigest", True),
        commit_hash=("spec.revision.git.commit", False),
        repo_url=("spec.source.git.uri", False),
        committer=("spec.revision.git.author.name", False),
    )

    _ANNOTATION_MAPPIG = dict(
        repo_url="io.openshift.build.source-location",
        commit_hash="io.openshift.build.commit.id",
        commit_time="io.openshift.build.commit.date",
    )


def commit_metric_from_build(app: str, build, errors: list) -> CommitMetric:
    """
    Create a CommitMetric from build information.
    Will collect errors for missing data instead of failing early.
    """
    # set attributes based on a mapping from attribute name to
    # lookup path.
    # Collect all errors to be reported at once instead of failing fast.
    metric = CommitMetric(app)
    for attr_name, (path, required) in CommitMetric._BUILD_MAPPING.items():
        with collect_bad_attribute_path_error(errors, required):
            value = get_nested(build, path, name="build")
            setattr(metric, attr_name, value)

    return metric


@attrs.frozen
class GitRepo:
    "Extracted information about a git repo url."

    url: str
    """
    The full URL for the repo.
    Obtained from build metadata, Image annotations, etc.
    """
    protocol: str
    fqdn: str
    group: str
    name: str
    "The git repo name, e.g. myrepo.git"
    port: Optional[str]

    @property
    def project(self) -> str:
        "Alias for the repo name."
        return self.name

    @property
    def server(self) -> str:
        "The protocol, server FQDN, and port in URL format."
        url = f"{self.protocol}://{self.fqdn}"

        if self.port:
            url += f":{self.port}"

        return url

    @classmethod
    def from_url(cls, url: str):
        "Parse the given URL and handle the edge cases for it."

        # code inherited from old committime metric class.
        # Unsure of the purpose of some of this code.

        # Ensure git URI does not end with "/", issue #590
        url = url.strip("/")
        parsed = giturlparse.parse(url)
        if len(parsed.protocols) > 0 and parsed.protocols[0] not in SUPPORTED_PROTOCOLS:
            raise ValueError("Unsupported protocol %s", parsed.protocols[0])
        protocol = parsed.protocol
        # In the case of multiple subgroups the host will be in the pathname
        # Otherwise, it will be in the resource
        if parsed.pathname.startswith("//"):
            fqdn = parsed.pathname.split("/")[2]
            protocol = parsed.protocols[0]
        else:
            fqdn = parsed.resource
        group = parsed.owner
        name = parsed.name
        port = parsed.port

        return cls(url, protocol, fqdn, group, name, port)


class CommitInfo(NamedTuple):
    """
    Information used to retrieve commit time information.
    Previously, this information wasn't guaranteed to be present,
    which made the code messy with various checks and exceptions, etc.
    Or worse, just hoping things weren't None and we wouldn't crash the exporter.

    In addition, it was unclear how exporters should report the commit time:
    they change it on the metric, but also return the metric,
    but if they return None, it shouldn't be counted... confusing.
    This allows us to handle things more consistently.
    """

    repo: GitRepo
    commit_hash: str


__all__ = ["CommitMetric"]

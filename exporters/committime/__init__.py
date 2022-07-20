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
from typing import Optional

import attr
import giturlparse

from pelorus.utils import collect_bad_attribute_path_error, get_nested

SUPPORTED_PROTOCOLS = {"http", "https", "ssh", "git"}


# TODO: the majority of these fields are unused.
# Let's figure out why they're there.
@attr.define
class CommitMetric:
    name: str = attr.field()
    annotations: dict = attr.field(default=None, kw_only=True)
    labels: dict = attr.field(default=None, kw_only=True)
    namespace: Optional[str] = attr.field(default=None, kw_only=True)

    __repo_url: str = attr.field(default=None, init=False)
    __repo_protocol = attr.field(default=None, init=False)
    __repo_fqdn: str = attr.field(default=None, init=False)
    __repo_group = attr.field(default=None, init=False)
    __repo_name = attr.field(default=None, init=False)
    __repo_project = attr.field(default=None, init=False)

    committer: Optional[str] = attr.field(default=None, kw_only=True)
    commit_hash: Optional[str] = attr.field(default=None, kw_only=True)
    commit_time: Optional[str] = attr.field(default=None, kw_only=True)
    commit_timestamp: Optional[float] = attr.field(default=None, kw_only=True)

    build_name: Optional[str] = attr.field(default=None, kw_only=True)
    build_config_name: Optional[str] = attr.field(default=None, kw_only=True)

    image_location: Optional[str] = attr.field(default=None, kw_only=True)
    image_name: Optional[str] = attr.field(default=None, kw_only=True)
    image_tag: Optional[str] = attr.field(default=None, kw_only=True)
    image_hash: Optional[str] = attr.field(default=None, kw_only=True)

    @property
    def repo_url(self):
        return self.__repo_url

    @repo_url.setter
    def repo_url(self, value):
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
        return str(self.__repo_protocol + "://" + self.__repo_fqdn)

    def __parse_repourl(self):
        """Parse the repo_url into individual pieces"""
        logging.debug("repo url = %s", self.__repo_url)
        if self.__repo_url is None:
            return
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

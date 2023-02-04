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

from datetime import datetime
from typing import NamedTuple, Optional

import attrs
import giturlparse

DEFAULT_PROVIDER = "git"
PROVIDER_TYPES = {"git", "image"}
GIT_PROVIDER_TYPES = {"github", "bitbucket", "gitea", "azure-devops", "gitlab"}

SUPPORTED_PROTOCOLS = {"http", "https", "ssh", "git"}


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


@attrs.define
class CommitMetric:
    name: str
    namespace: str = attrs.field(kw_only=True)

    commit_hash: str = attrs.field(kw_only=True)

    commit_timestamp: datetime = attrs.field(kw_only=True)

    image_hash: str = attrs.field(kw_only=True)

    # TODO: move to collector_image
    _ANNOTATION_MAPPING = dict(
        repo_url="io.openshift.build.source-location",
        commit_hash="io.openshift.build.commit.id",
        commit_time="io.openshift.build.commit.date",
    )


__all__ = ["CommitMetric", "GitRepo", "CommitInfo"]

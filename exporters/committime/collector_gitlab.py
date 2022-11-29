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

import logging

import gitlab
import requests
from attrs import define, field

from committime import CommitInfo
from pelorus.timeutil import parse_tz_aware
from pelorus.utils import set_up_requests_session

from .collector_base import AbstractGitCommitCollector, UnsupportedGITProvider

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"


@define(kw_only=True)
class GitLabCommitCollector(AbstractGitCommitCollector):
    session: requests.Session = field(factory=requests.Session, init=False)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        set_up_requests_session(
            self.session, self.tls_verify, username=self.username, token=self.token
        )

    def _connect_to_gitlab(self, git_server: str) -> gitlab.Gitlab:
        """Method to connect to Gitlab instance."""
        gitlab_client = None

        if self.token:
            # Private or personal token
            logging.debug("Connecting to GitLab server using token: %s", (git_server))
            gitlab_client = gitlab.Gitlab(
                git_server,
                private_token=self.token,
                api_version="4",
                session=self.session,
            )
        else:
            # Public repo without token
            logging.debug("Connecting to GitLab server without token: %s", (git_server))
            gitlab_client = gitlab.Gitlab(
                git_server, api_version="4", session=self.session
            )

        return gitlab_client

    def get_commit_time(self, info: CommitInfo):
        """Method called to collect data and send to Prometheus"""

        repo, hash = info
        git_server = repo.server

        if (
            "github" in git_server
            or "gitea" in git_server
            or "bitbucket" in git_server
            or "azure" in git_server
        ):
            raise UnsupportedGITProvider(
                "Skipping non GitLab server, found %s" % (git_server)
            )

        gl = self._connect_to_gitlab(git_server)
        if not gl:
            return None

        project_namespaced = f"{repo.group}/{repo.name}"

        project = None

        try:
            logging.debug("Getting project: %s", project_namespaced)
            project = gl.projects.get(project_namespaced)
        except Exception:
            logging.error(
                "Failed to get project: %s, repo: %s",
                repo.url,
                repo.name,
                exc_info=True,
            )
            raise
        try:
            # get the commit from the project using the hash
            short_hash = hash[:8]
            commit = project.commits.get(short_hash)

            commit_time_str: str = (
                commit.committed_date
            )  # assumed based on `__getattr__` in RESTObject
            return parse_tz_aware(commit_time_str, format=_DATETIME_FORMAT)
        except Exception:
            logging.error(
                "Failed processing commit time",
                exc_info=True,
            )
            raise

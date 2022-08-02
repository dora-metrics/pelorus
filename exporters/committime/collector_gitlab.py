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
from collector_base import AbstractCommitCollector, UnsupportedGITProvider

import pelorus


class GitLabCommitCollector(AbstractCommitCollector):
    def __init__(self, kube_client, username, token, namespaces, apps):
        super().__init__(
            kube_client,
            username,
            token,
            namespaces,
            apps,
            "GitLab",
            "%Y-%m-%dT%H:%M:%S.%f%z",
        )

    def _connect_to_gitlab(self, metric) -> gitlab.Gitlab:
        """Method to connect to Gitlab instance."""
        git_server = metric.git_server

        gitlab_client = None

        session = requests.Session()
        session.verify = False

        if self._token:
            # Private or personal token
            logging.debug("Connecting to GitLab server using token: %s" % (git_server))
            gitlab_client = gitlab.Gitlab(
                git_server, private_token=self._token, api_version=4, session=session
            )
        else:
            # Public repo without token
            logging.debug(
                "Connecting to GitLab server without token: %s" % (git_server)
            )
            gitlab_client = gitlab.Gitlab(git_server, api_version=4, session=session)

        return gitlab_client

    # base class impl
    def get_commit_time(self, metric):
        """Method called to collect data and send to Prometheus"""

        git_server = metric.git_server

        if (
            "github" in git_server
            or "gitea" in git_server
            or "bitbucket" in git_server
            or "azure" in git_server
        ):
            raise UnsupportedGITProvider(
                "Skipping non GitLab server, found %s" % (git_server)
            )

        gl = self._connect_to_gitlab(metric)
        if not gl:
            return None

        project_namespace = metric.repo_group
        project_name = metric.repo_project

        # namespaced project allows to get it by it's name
        project_namespaced = "%s/%s" % (project_namespace, project_name)

        project = None

        try:
            logging.debug("Getting project: %s" % (project_namespaced))
            project = gl.projects.get(project_namespaced)
        except Exception:
            logging.error(
                "Failed to get project: %s, repo: %s for build %s"
                % (metric.repo_url, project_name, metric.build_name),
                exc_info=True,
            )
            raise
        try:
            # get the commit from the project using the hash
            short_hash = metric.commit_hash[:8]
            commit = project.commits.get(short_hash)
            # get the commit date/time
            metric.commit_time = commit.committed_date
            # set the timestamp after conversion
            metric.commit_timestamp = pelorus.convert_date_time_to_timestamp(
                metric.commit_time, self._timedate_format
            )
        except Exception:
            logging.error(
                "Failed processing commit time for build %s" % metric.build_name,
                exc_info=True,
            )
            raise
        return metric

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
from collections import OrderedDict

import gitlab
import requests
from attrs import define, field

from committime import CommitMetric, sanitize_url
from pelorus.timeutil import parse_tz_aware
from pelorus.utils import set_up_requests_session

from .collector_base import AbstractCommitCollector, git_api_errors, check_provider_support

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"


@define(kw_only=True)
class GitLabCommitCollector(AbstractCommitCollector):
    session: requests.Session = field(factory=requests.Session, init=False)

    _gitlab_clients: dict[str, gitlab.Gitlab] = field(factory=dict, init=False)

    _project_cache: OrderedDict[tuple[str, str], object] = field(factory=OrderedDict, init=False)

    _PROJECT_CACHE_MAX = 1_000

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        set_up_requests_session(
            self.session, self.tls_verify, username=self.username, token=self.token
        )

    def _connect_to_gitlab(self, metric) -> gitlab.Gitlab:
        """Return a cached or new GitLab client for the metric's git server."""
        git_server = metric.git_server

        with self._cache_lock:
            if git_server in self._gitlab_clients:
                return self._gitlab_clients[git_server]

        if self.token:
            logging.debug("Connecting to GitLab server (authenticated): %s", git_server)
            gitlab_client = gitlab.Gitlab(
                git_server,
                private_token=self.token,
                api_version=4,
                session=self.session,
                timeout=self._API_TIMEOUT,
            )
        else:
            logging.debug(
                "Connecting to GitLab server (unauthenticated): %s", git_server
            )
            gitlab_client = gitlab.Gitlab(
                git_server, api_version=4, session=self.session, timeout=self._API_TIMEOUT
            )

        with self._cache_lock:
            return self._gitlab_clients.setdefault(git_server, gitlab_client)

    def get_commit_time(self, metric: CommitMetric):
        """Fetch commit timestamp from GitLab API for the given metric."""

        git_server = metric.git_server

        check_provider_support(git_server, "gitlab")

        gl = self._connect_to_gitlab(metric)

        project_namespace = metric.repo_group
        project_name = metric.repo_project

        # namespaced project allows fetching by name
        project_namespaced = f"{project_namespace}/{project_name}"

        cache_key = (git_server, project_namespaced)
        with self._cache_lock:
            project = self._project_cache.get(cache_key)
            if project is not None:
                self._project_cache.move_to_end(cache_key)

        if project is None:
            try:
                logging.debug("Getting project: %s", project_namespaced)
                project = gl.projects.get(project_namespaced)
                with self._cache_lock:
                    if len(self._project_cache) >= self._PROJECT_CACHE_MAX:
                        self._project_cache.popitem(last=False)
                    self._project_cache[cache_key] = project
            except (gitlab.exceptions.GitlabError, requests.exceptions.RequestException) as exc:
                git_api_errors.inc()
                logging.error(
                    "Failed to get project: %s, repo: %s for build %s",
                    sanitize_url(metric.repo_url), project_name, metric.build_name,
                    exc_info=True,
                )
                raise
        try:
            commit = project.commits.get(metric.commit_hash)

            commit_time_str: str = commit.committed_date
            metric.commit_time = commit_time_str
            metric.commit_timestamp = parse_tz_aware(
                commit_time_str, format=_DATETIME_FORMAT
            ).timestamp()
            metric.commit_link = commit.web_url
        except (gitlab.exceptions.GitlabError, requests.exceptions.RequestException, KeyError, AttributeError, ValueError) as exc:
            git_api_errors.inc()
            logging.error(
                "Failed processing commit time for build %s",
                metric.build_name,
                exc_info=True,
            )
            raise
        return metric

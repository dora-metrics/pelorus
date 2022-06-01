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
import time

from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

import pelorus
from failure.collector_base import AbstractFailureCollector
from failure.collector_github import GithubFailureCollector
from failure.collector_jira import JiraFailureCollector
from failure.collector_servicenow import ServiceNowFailureCollector

PROVIDER_TYPES = ["jira", "github", "servicenow"]


class TrackerFactory:
    @staticmethod
    def getCollector() -> AbstractFailureCollector:
        username = pelorus.utils.get_env_var("USER")
        token = pelorus.utils.get_env_var("TOKEN")
        tracker_api = pelorus.utils.get_env_var("SERVER")
        tracker_provider = pelorus.utils.get_env_var(
            "PROVIDER", pelorus.DEFAULT_TRACKER
        )

        projects = pelorus.utils.get_env_var("PROJECTS") or ""
        if projects:
            logging.info("Querying issues from '%s' projects.", projects)
            projects = projects.replace(" ", ",")
        else:
            logging.warning("No PROJECTS given")

        if tracker_provider == "jira":
            pelorus.utils.check_required_config(JiraFailureCollector.REQUIRED_CONFIG)
            return JiraFailureCollector(
                server=tracker_api,
                user=username,
                apikey=token,
                projects=projects,
            )
        elif tracker_provider == "servicenow":
            pelorus.utils.check_required_config(
                ServiceNowFailureCollector.REQUIRED_CONFIG
            )
            return ServiceNowFailureCollector(username, token, tracker_api)
        elif tracker_provider == "github":
            pelorus.utils.check_required_config(GithubFailureCollector.REQUIRED_CONFIG)
            return GithubFailureCollector(
                apikey=token, projects=projects, server=tracker_api
            )

        raise ValueError(f"Unknown provider type {tracker_provider}")


if __name__ == "__main__":
    logging.info("===== Starting Failure Collector =====")

    collector = TrackerFactory.getCollector()

    logging.info("Server: " + collector.server)
    logging.info(f"User: {collector.user}")
    start_http_server(8080)

    REGISTRY.register(collector)

    while True:
        time.sleep(1)
    logging.info("===== Exit Failure Collector =====")

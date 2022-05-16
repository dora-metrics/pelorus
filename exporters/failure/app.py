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
import os
import time
from typing import Union

from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

import pelorus
from failure.collector_jira import JiraFailureCollector
from failure.collector_servicenow import ServiceNowFailureCollector

REQUIRED_CONFIG = ["CONFIG_REQUIRED_FOR_ALL"]


class TrackerFactory:
    @staticmethod
    def getCollector(
        username, token, tracker_api, projects, tracker_provider
    ) -> Union[JiraFailureCollector, ServiceNowFailureCollector]:
        if tracker_provider == "jira":
            pelorus.utils.check_required_config(JiraFailureCollector.REQUIRED_CONFIG)
            return JiraFailureCollector(
                server=tracker_api, user=username, apikey=token, projects=projects
            )
        elif tracker_provider == "servicenow":
            pelorus.utils.check_required_config(
                ServiceNowFailureCollector.REQUIRED_CONFIG
            )
            return ServiceNowFailureCollector(username, token, tracker_api)
        else:
            raise ValueError(f"Unknown provider {tracker_provider}")


if __name__ == "__main__":
    logging.info("===== Starting Failure Collector =====")
    pelorus.utils.check_required_config(REQUIRED_CONFIG)
    projects = None
    if os.environ.get("PROJECTS") is not None:
        logging.info(
            "Querying issues from '%s' projects.",
            os.environ.get("PROJECTS"),
        )
        projects = os.environ.get("PROJECTS")
    username = os.environ.get("USER")
    token = os.environ.get("TOKEN")
    tracker_api = os.environ.get("SERVER")
    tracker_provider = os.environ.get("PROVIDER", pelorus.DEFAULT_TRACKER)
    logging.info("Server: " + tracker_api)
    logging.info("User: " + username)
    start_http_server(8080)

    collector = TrackerFactory.getCollector(
        username, token, tracker_api, projects, tracker_provider
    )

    REGISTRY.register(collector)

    while True:
        time.sleep(1)
    logging.info("===== Exit Failure Collector =====")

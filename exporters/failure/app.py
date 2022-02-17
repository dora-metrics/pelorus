#!/usr/bin/env python3
import logging
import os
import sys
import time

from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

import pelorus
from failure.collector_jira import JiraFailureCollector
from failure.collector_servicenow import ServiceNowFailureCollector

REQUIRED_CONFIG = ["USER", "TOKEN", "SERVER"]


class TrackerFactory:
    @staticmethod
    def getCollector(username, token, tracker_api, projects, tracker_provider):
        if tracker_provider == "jira":
            return JiraFailureCollector(username, token, tracker_api, projects)
        if tracker_provider == "servicenow":
            return ServiceNowFailureCollector(username, token, tracker_api)


if __name__ == "__main__":
    logging.info("===== Starting Failure Collector =====")
    if pelorus.missing_configs(REQUIRED_CONFIG):
        print("This program will exit.")
        sys.exit(1)
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

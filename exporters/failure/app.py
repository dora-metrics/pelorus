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

import time

from attrs import field, frozen
from attrs.validators import in_
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

import pelorus
from failure.collector_azure_devops import AzureDevOpsFailureCollector
from failure.collector_base import AbstractFailureCollector
from failure.collector_github import GitHubFailureCollector
from failure.collector_jira import JiraFailureCollector
from failure.collector_pagerduty import PagerDutyFailureCollector
from failure.collector_servicenow import ServiceNowFailureCollector
from pelorus.config import env_vars, load_and_log

PROVIDER_TYPES = {
    "jira": JiraFailureCollector,
    "github": GitHubFailureCollector,
    "servicenow": ServiceNowFailureCollector,
    "pagerduty": PagerDutyFailureCollector,
    "azure-devops": AzureDevOpsFailureCollector,
}


@frozen
class FailureCollectorConfig:
    tracker_provider: str = field(
        default=pelorus.DEFAULT_TRACKER,
        metadata=env_vars("PROVIDER"),
        validator=in_(PROVIDER_TYPES.keys()),
    )

    def create(self):
        return load_and_log(PROVIDER_TYPES[self.tracker_provider])


def set_up(prod: bool = True) -> AbstractFailureCollector:
    pelorus.setup_logging(prod=prod)

    config = load_and_log(FailureCollectorConfig)
    collector = config.create()

    REGISTRY.register(collector)
    return collector


if __name__ == "__main__":
    import logging

    try:
        set_up()
        pelorus.mark_startup(True)
    except Exception as e:
        pelorus.mark_startup(False)
        logging.error(
            "Failed to configure failure exporter: %s. "
            "Set PROVIDER (jira/github/servicenow/pagerduty/azure-devops) "
            "and required provider settings (e.g. SERVER, TOKEN). "
            "Starting metrics server anyway - configure and restart to collect failure data.",
            e,
            exc_info=True,
        )

    start_http_server(pelorus.EXPORTER_PORT)
    logging.info("Failure exporter ready, serving metrics on :%d", pelorus.EXPORTER_PORT)

    while True:
        time.sleep(60)

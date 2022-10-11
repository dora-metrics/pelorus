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
from failure.collector_github import GithubFailureCollector
from failure.collector_jira import JiraFailureCollector
from failure.collector_servicenow import ServiceNowFailureCollector
from pelorus.config import env_vars, load_and_log

PROVIDER_TYPES = {"jira", "github", "servicenow"}


@frozen
class FailureCollectorConfig:
    tracker_provider: str = field(
        default=pelorus.DEFAULT_TRACKER,
        metadata=env_vars("PROVIDER"),
        validator=in_(PROVIDER_TYPES),
    )

    def create(self):
        if self.tracker_provider == "jira":
            return load_and_log(JiraFailureCollector)
        elif self.tracker_provider == "servicenow":
            return load_and_log(ServiceNowFailureCollector)
        elif self.tracker_provider == "github":
            return load_and_log(GithubFailureCollector)
        else:
            raise ValueError(
                "unknown tracker {self.tracker_provider}, but should be unreachable because of attrs"
            )


if __name__ == "__main__":
    pelorus.setup_logging()

    config = load_and_log(FailureCollectorConfig)
    collector = config.create()

    REGISTRY.register(collector)
    start_http_server(8080)

    while True:
        time.sleep(1)

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
from typing import Dict, Optional

import requests
from attrs import define, field

from failure.collector_base import AbstractFailureCollector, TrackerIssue
from pelorus.config import env_var_names, env_vars
from pelorus.config.converters import comma_or_whitespace_separated
from pelorus.config.log import REDACT, log
from pelorus.errors import FailureProviderAuthenticationError
from pelorus.timeutil import parse_assuming_utc, second_precision
from pelorus.utils import TokenAuth, set_up_requests_session

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@define(kw_only=True)
class PagerdutyFailureCollector(AbstractFailureCollector):
    """
    PagerDuty implementation of a FailureCollector
    """

    token: str = field(
        default="",
        metadata=env_vars(*env_var_names.TOKEN) | log(REDACT),
        repr=False,
    )

    tls_verify: bool = field(default=True)

    session: requests.Session = field(factory=requests.Session, init=False)

    incident_urgency: set[str] = field(
        factory=set,
        converter=comma_or_whitespace_separated(set),
        metadata=env_vars("PAGERDUTY_URGENCY"),
    )

    incident_priority: set[str] = field(
        factory=set,
        converter=comma_or_whitespace_separated(set),
        metadata=env_vars("PAGERDUTY_PRIORITY"),
    )

    url = "https://api.pagerduty.com/incidents?date_range=all&limit=10000"
    headers = {"Accept": "application/vnd.pagerduty+json;version=2"}

    def __attrs_post_init__(self):
        # disable .netrc
        self.session.trust_env = False

        if self.token:
            set_up_requests_session(
                self.session,
                self.tls_verify,
                auth=TokenAuth(self.token, is_pagerduty=True),
            )

    def get_incidents(self) -> list[dict]:
        logging.info("Getting incidents")

        resp = self.session.get(self.url, headers=self.headers)
        try:
            resp.raise_for_status()
            # TODO too much noise?
            logging.debug("PagerDuty successfully returned %s", resp.text)
            return resp.json()["incidents"]
        except requests.HTTPError as error:
            if resp.status_code == requests.codes.unauthorized:
                raise FailureProviderAuthenticationError from error
            raise  # pragma: no cover

    def filter_by_urgency(self, urgency: str) -> bool:
        if not self.incident_urgency:
            return True
        return urgency in self.incident_urgency

    def filter_by_priority(self, priority: Optional[Dict[str, str]]) -> bool:
        if not self.incident_priority:
            return True
        try:
            return priority["summary"] in self.incident_priority
        except TypeError:
            # Incidents without priority come as None, instead of dict
            return "null" in self.incident_priority

    def search_issues(self) -> list[TrackerIssue]:
        """
        To maintain consistency, we call this method `search_issues`. An
        `issue` in PagerDuty is called `incident`.
        """
        production_incidents = []
        for incident in self.get_incidents():
            is_production_bug = self.filter_by_urgency(
                incident["urgency"]
            ) and self.filter_by_priority(incident["priority"])

            if is_production_bug:
                created_at = incident["created_at"]
                resolved_at = incident["last_status_change_at"]
                incident_id = incident["incident_number"]
                title = incident["title"]

                created_tz = parse_assuming_utc(created_at, _DATETIME_FORMAT)
                created_ts = second_precision(created_tz).timestamp()

                resolution_tz = parse_assuming_utc(resolved_at, _DATETIME_FORMAT)
                resolution_ts = second_precision(resolution_tz).timestamp()

                if resolution_ts > created_ts:
                    logging.debug(
                        "Found production incident closed: {}, {}: {}".format(
                            resolved_at,
                            incident_id,
                            title,
                        )
                    )
                else:
                    logging.debug(
                        "Found production incident opened: {}, {}: {}".format(
                            created_at,
                            incident_id,
                            title,
                        )
                    )
                    resolution_ts = None

                tracker_issue = TrackerIssue(
                    str(incident_id),
                    created_ts,
                    resolution_ts,
                    incident["service"]["summary"],
                    # TODO another thing I thought: we could filter services
                    # (did not think about a good use case for this) or have a
                    # map like user inputs pairs of key values, like
                    #    key1=value1,key2=value2
                    # and then pelorus will put the app here as the value. Ex.:
                    # the service is named "Incidents of production" but the app
                    # is called "todolist", then we could map the incidents to the right app
                )
                production_incidents.append(tracker_issue)
        if not production_incidents:
            # TODO should be warning?
            logging.debug("No issues were found")
        return production_incidents

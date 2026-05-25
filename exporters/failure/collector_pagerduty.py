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
from typing import Optional

import requests
from attrs import converters, define, field

from failure.collector_base import (
    AbstractFailureCollector,
    FailureProviderAuthenticationError,
    TrackerIssue,
    _issue_parse_failures,
)
from pelorus.config import env_var_names, env_vars
from pelorus.config.converters import comma_or_whitespace_separated
from pelorus.config.log import REDACT, log
from pelorus.timeutil import ISO_ZULU_FMT, parse_assuming_utc, second_precision
from pelorus.utils import TokenAuth, set_up_requests_session


@define(kw_only=True)
class PagerDutyFailureCollector(AbstractFailureCollector):
    """
    PagerDuty implementation of a FailureCollector
    """

    token: str = field(
        default="",
        metadata=env_vars(*env_var_names.TOKEN) | log(REDACT),
        repr=False,
    )

    tls_verify: bool = field(default=True, converter=converters.to_bool)

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

    _BASE_URL = "https://api.pagerduty.com/incidents"
    _PAGE_LIMIT = 100
    headers = {"Accept": "application/vnd.pagerduty+json;version=2"}

    def __attrs_post_init__(self):
        if self.token:
            set_up_requests_session(
                self.session,
                self.tls_verify,
                auth=TokenAuth(self.token, is_pagerduty=True),
            )
        else:
            logging.warning(
                "No TOKEN configured for PagerDuty. API calls will fail with 401. "
                "Set TOKEN to a valid PagerDuty API token."
            )

    def get_incidents(self) -> list[dict]:
        logging.debug("Collecting incidents")

        all_incidents = []
        offset = 0

        while True:
            params = {
                "date_range": "all",
                "limit": str(self._PAGE_LIMIT),
                "offset": str(offset),
            }
            resp = self.session.get(
                self._BASE_URL, headers=self.headers, params=params, timeout=30
            )
            try:
                resp.raise_for_status()
                data = resp.json()
                if "incidents" not in data:
                    raise RuntimeError(
                        f"PagerDuty response missing 'incidents' key (keys: {list(data.keys())})"
                    )
                incidents = data["incidents"]
                all_incidents.extend(incidents)
                logging.debug(
                    "PagerDuty returned %d incidents (offset=%d, more=%s)",
                    len(incidents),
                    offset,
                    data.get("more", False),
                )
                if not data.get("more", False):
                    break
                offset += self._PAGE_LIMIT
            except requests.JSONDecodeError:
                logging.error("Invalid JSON response from PagerDuty (offset=%d)", offset, exc_info=True)
                raise
            except requests.HTTPError as error:
                if resp.status_code == requests.codes.unauthorized:
                    logging.error(FailureProviderAuthenticationError.auth_message)
                    raise FailureProviderAuthenticationError from error
                logging.error("PagerDuty API request failed: %s", error, exc_info=True)  # pragma: no cover
                raise  # pragma: no cover

        return all_incidents

    def filter_by_urgency(self, urgency: str) -> bool:
        if not self.incident_urgency:
            return True
        return urgency in self.incident_urgency

    def filter_by_priority(self, priority: Optional[dict[str, str]]) -> bool:
        if not self.incident_priority:
            return True
        try:
            return priority["summary"] in self.incident_priority
        except TypeError:
            # Incidents without priority come as None, instead of dict
            logging.debug("Incident priority is None, checking if 'null' is in configured priorities")
            return "null" in self.incident_priority

    def search_issues(self) -> list[TrackerIssue]:
        """
        To maintain consistency, we call this method `search_issues`. An
        `issue` in PagerDuty is called `incident`.
        """
        production_incidents = []
        all_incidents = self.get_incidents()
        total_count = len(all_incidents)
        skipped = 0
        for incident in all_incidents:
            try:
                is_production_bug = self.filter_by_urgency(
                    incident["urgency"]
                ) and self.filter_by_priority(incident["priority"])

                if is_production_bug:
                    created_at = incident["created_at"]
                    resolved_at = incident["last_status_change_at"]
                    incident_id = incident["incident_number"]

                    created_tz = parse_assuming_utc(created_at, ISO_ZULU_FMT)
                    created_ts = second_precision(created_tz).timestamp()

                    resolution_tz = parse_assuming_utc(resolved_at, ISO_ZULU_FMT)
                    resolution_ts = second_precision(resolution_tz).timestamp()

                    if resolution_ts > created_ts:
                        logging.debug(
                            "Found production incident closed: %s, %s",
                            resolved_at,
                            incident_id,
                        )
                    else:
                        logging.debug(
                            "Found production incident opened: %s, %s",
                            created_at,
                            incident_id,
                        )
                        resolution_ts = None

                    tracker_issue = TrackerIssue(
                        str(incident_id),
                        created_ts,
                        resolution_ts,
                        incident["service"]["summary"],
                    )
                    production_incidents.append(tracker_issue)
            except Exception:
                skipped += 1
                _issue_parse_failures.inc()
                logging.error(
                    "Failed to parse PagerDuty incident %s, skipping",
                    incident.get("incident_number", "unknown"),
                    exc_info=True,
                )
        if skipped:
            logging.warning("Skipped %d unparseable PagerDuty incidents", skipped)
        if not production_incidents:
            logging.debug("No matching incidents found out of %d total", total_count)
        else:
            logging.info(
                "Found %d matching incidents out of %d total",
                len(production_incidents), total_count,
            )
        return production_incidents

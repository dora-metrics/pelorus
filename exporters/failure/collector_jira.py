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
from datetime import datetime

import pytz
from jira import JIRA
from jira.exceptions import JIRAError

import pelorus
from failure.collector_base import AbstractFailureCollector, TrackerIssue

# One query limit, exporter will query multiple times.
# Do not exceed 100 as JIRA won't return more.
JIRA_SEARCH_RESULTS = 50


class JiraFailureCollector(AbstractFailureCollector):
    REQUIRED_CONFIG = ["USER", "TOKEN", "SERVER", "OTHERCONFIG"]

    """
    Jira implementation of a FailureCollector
    """

    def __init__(self, user, apikey, server, projects):

        super().__init__(server, user, apikey)
        self.projects = projects

    def _connect_to_jira(self) -> JIRA:
        """Method to connect to JIRA instance which may be cloud based
        or self-hosted.
        """
        jira_client = None
        server = self.server
        email = self.user
        api_key = self.apikey

        # Connect to Jira
        jira_client = JIRA(options={"server": server}, basic_auth=(email, api_key))

        # Ensure connection was performed
        try:
            jira_client.session()
        except JIRAError as error:
            logging.error(
                "Status: %s, Error Response: %s", error.status_code, error.text
            )
            raise

        return jira_client

    def search_issues(self):
        jira = self._connect_to_jira()

        critical_issues = []

        try:
            # TODO FIXME This may need to be modified to suit needs and have a time period.
            query_string = "type=bug and priority=highest"
            query_result_fields = "summary,labels,created,resolutiondate"

            if self.projects is not None:
                query_string = query_string + " AND project in (" + self.projects + ")"

            jira_issues = []
            start_at = 0
            while True:
                jira_search_results = jira.search_issues(
                    query_string,
                    startAt=start_at,
                    maxResults=JIRA_SEARCH_RESULTS,
                    fields=query_result_fields,
                )
                jira_issues += jira_search_results.iterable
                start_at += JIRA_SEARCH_RESULTS
                logging.info("Getting jira results: %s" % start_at)
                if start_at >= jira_search_results.total:
                    break

            for issue in jira_issues:
                logging.debug(issue)
                logging.debug(
                    "Found issue opened: {}, {}: {}".format(
                        str(issue.fields.created), issue.key, issue.fields.summary
                    )
                )
                # Create the JiraFailureMetric
                created_ts = self.convert_timestamp(issue.fields.created)
                resolution_ts = None
                if issue.fields.resolutiondate:
                    logging.debug(
                        "Found issue close: {}, {}: {}".format(
                            str(issue.fields.resolutiondate),
                            issue.key,
                            issue.fields.summary,
                        )
                    )
                    resolution_ts = self.convert_timestamp(issue.fields.resolutiondate)
                tracker_issue = TrackerIssue(
                    issue.key, created_ts, resolution_ts, self.get_app_name(issue)
                )
                critical_issues.append(tracker_issue)
        except JIRAError as error:
            if error.status_code == 400:
                logging.error(
                    "Status: %s, Error Response: %s", error.status_code, error.text
                )
                logging.info("JIRA query: %s", query_string)
            else:
                raise

        return critical_issues

    def convert_timestamp(self, date_time):
        """Convert a Jira datetime with TZ to UTC"""
        # The time retunred by Jira has a TZ, so convert to UTC
        utc = datetime.strptime(date_time, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(
            pytz.utc
        )
        # Change the datetime to a string
        utc_string = utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        # convert to timestamp
        return pelorus.convert_date_time_to_timestamp(utc_string)

    def get_app_name(self, issue):
        app_label = pelorus.get_app_label()
        for label in issue.fields.labels:
            if label.startswith("%s=" % app_label):
                return label.replace("%s=" % app_label, "")
        return "unknown"

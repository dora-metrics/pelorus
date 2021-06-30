import logging
from datetime import datetime

import pytz
from collector_base import AbstractFailureCollector, TrackerIssue
from jira import JIRA

import pelorus


class JiraFailureCollector(AbstractFailureCollector):
    """
    Jira implementation of a FailureCollector
    """

    def __init__(self, user, apikey, server):
        super().__init__(server, user, apikey)

    def search_issues(self):
        options = {"server": self.server}
        # Connect to Jira
        jira = JIRA(options, basic_auth=(self.user, self.apikey))
        # TODO FIXME This may need to be modified to suit needs and have a time period.
        query_string = "type=bug and priority=highest"
        jira = JIRA(options, basic_auth=(self.user, self.apikey))
        jira_issues = jira.search_issues(query_string)
        critical_issues = []
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

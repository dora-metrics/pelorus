from collector_base import AbstractFailureCollector, FailureMetric, TrackerIssue
import logging
import pelorus
import pytz
from jira import JIRA
from datetime import datetime


class JiraFailureCollector(AbstractFailureCollector):
    """
    Jira implementation of a FailureCollector
    """

    def __init__(self, user, apikey, server,project='MDT'):
        super().__init__(server, user, apikey, project)

    def search_issues(self):
        options = {
            'server': self.server
        }
        # Connect to Jira
        jira = JIRA(options, basic_auth=(self.user, self.apikey))
        # TODO FIXME This may need to be modified to suit needs and have a time period.
        query_string = "project=" + self.project + " and type=bug and priority=highest"
        jira = JIRA(options, basic_auth=(self.user, self.apikey))
        jira_issues = jira.search_issues(query_string)
        critical_issues = []
        for issue in jira_issues:
            logging.info('Found issue opened: {}, {}: {}'.format(str(issue.fields.created), issue.key, issue.fields.summary))
            # Create the JiraFailureMetric
            created_ts = self.convert_timestamp(issue.fields.created)
            resolution_ts = None
            if issue.fields.resolutiondate:
                logging.info('Found issue close: {}, {}: {}'.format(str(issue.fields.resolutiondate), issue.key, issue.fields.summary))
                resolution_ts = self.convert_timestamp(issue.fields.resolutiondate)
            tracker_issue = TrackerIssue(issue.key, created_ts, resolution_ts)
            critical_issues.append(tracker_issue)

        return critical_issues


    def convert_timestamp(self, date_time):
        """Convert a Jira datetime with TZ to UTC """
        # The time retunred by Jira has a TZ, so convert to UTC
        utc = datetime.strptime(date_time, '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(pytz.utc)
        # Change the datetime to a string
        utc_string = utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        # convert to timestamp
        return pelorus.convert_date_time_to_timestamp(utc_string)


from collector_base import AbstractFailureCollector, TrackerIssue
import logging
import pelorus
import pytz
import requests
import os
from datetime import datetime

SN_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
SN_QUERY = '/api/now/table/incident?sysparm_fields={0}%2C{1}%2Cstate%2Cnumber%2C{2} \
            &sysparm_display_value=true&sysparm_limit={3}&sysparm_offset={4}'
SN_OPENED_FIELD = "opened_at"
SN_RESOLVED_FIELD = "resolved_at"


class ServiceNowFailureCollector(AbstractFailureCollector):
    """
    Service Now implementation of a FailureCollector
    """

    def __init__(self, user, apikey, server):
        if not os.environ.get('APP_FIELD'):
            logging.warn("Missing Application Name Field Parameter defaulting to '%s'",
                         pelorus.DEFAULT_TRACKER_APP_FIELD)
            self.app_name_field = pelorus.DEFAULT_TRACKER_APP_FIELD
        self.app_name_field = os.environ.get('APP_FIELD')
        self.page_size = 100
        super().__init__(server, user, apikey)

    def search_issues(self):
        # Connect to ServiceNow
        self.offset = 0

        critical_issues = []
        data = self.query_servicenow()
        while len(data['result']) > 0:
            logging.debug("Returned %s Records, current offset is: %s", len(data['result']), self.offset)
            for issue in data['result']:
                logging.info('Found issue opened: %s, %s: %s', issue.get('number'),
                             issue.get(SN_OPENED_FIELD), issue.get(SN_RESOLVED_FIELD))
                # Create the FailureMetric
                created_ts = self.convert_timestamp(issue[SN_OPENED_FIELD])
                resolution_ts = None
                if issue[SN_RESOLVED_FIELD]:
                    logging.info('Found issue close: %s, %s: %s', issue.get(SN_RESOLVED_FIELD),
                                 issue.get('number'), issue.get(SN_OPENED_FIELD))
                    resolution_ts = self.convert_timestamp(issue.get(SN_RESOLVED_FIELD))
                tracker_issue = TrackerIssue(issue.get('number'), created_ts, resolution_ts, self.get_app_name(issue))
                critical_issues.append(tracker_issue)
            data = self.query_servicenow()

        return critical_issues

    def query_servicenow(self):
        self.tracker_query = SN_QUERY.format(SN_OPENED_FIELD, SN_RESOLVED_FIELD,
                                             self.app_name_field, self.page_size, self.offset)
        tracker_url = self.server + self.tracker_query

        # Do the HTTP request
        response = requests.get(tracker_url, auth=(self.user, self.apikey), headers=SN_HEADERS)
        # Check for HTTP codes other than 200

        if response.status_code != 200:
            logging.error("Status:, %s, Headers:, %s, Error Response: %s",
                          response.status_code, response.headers, response.json())
            raise RuntimeError("Error connecting to Service now")
        # Decode the JSON response into a dictionary and use the data
        data = response.json()
        logging.debug(data.get('result'))
        self.offset = self.offset + self.page_size
        return data

    def get_app_name(self, issue):
        if issue.get(self.app_name_field):
            app_label = issue.get(self.app_name_field)
            return app_label
        return pelorus.DEFAULT_TRACKER_APP_LABEL

    def convert_timestamp(self, date_time):
        """Convert a Jira datetime with TZ to UTC """
        # The time retunred by Jira has a TZ, so convert to UTC
        utc = datetime.strptime(date_time, '%Y-%m-%d %H:%M:%S').astimezone(pytz.utc)
        # Change the datetime to a string
        utc_string = utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        # convert to timestamp
        return pelorus.convert_date_time_to_timestamp(utc_string)

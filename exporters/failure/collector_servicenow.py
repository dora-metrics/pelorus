import logging

import requests
from attrs import define, field

import pelorus
from failure.collector_base import AbstractFailureCollector, TrackerIssue
from pelorus.config import REDACT, env_var_names, env_vars, log
from pelorus.timeutil import parse_assuming_utc, second_precision
from pelorus.utils import set_up_requests_session

SN_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
SN_QUERY = "/api/now/table/incident?sysparm_fields={0}%2C{1}%2Cstate%2Cnumber%2C{2} \
            &sysparm_display_value=true&sysparm_limit={3}&sysparm_offset={4}"
SN_OPENED_FIELD = "opened_at"
SN_RESOLVED_FIELD = "resolved_at"

_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

PAGE_SIZE = 100


@define(kw_only=True)
class ServiceNowFailureCollector(AbstractFailureCollector):
    """
    Service Now implementation of a FailureCollector
    """

    username: str = field(default="", metadata=env_vars(*env_var_names.USERNAME))

    token: str = field(
        default="",
        metadata=env_vars(*env_var_names.TOKEN) | log(REDACT),
        repr=False,
    )

    server: str = field(metadata=env_vars("SERVER"))

    app_name_field: str = field(
        default=pelorus.DEFAULT_TRACKER_APP_FIELD, metadata=env_vars("APP_FIELD")
    )

    tls_verify: bool = field(default=True)
    session: requests.Session = field(factory=requests.Session, init=False)

    offset: int = field(default=0, init=False)

    def __attrs_post_init__(self):
        set_up_requests_session(
            self.session, self.tls_verify, username=self.username, token=self.token
        )
        self.session.headers.update(SN_HEADERS)

    def search_issues(self):
        # Connect to ServiceNow
        self.offset = 0

        critical_issues = []
        data = self.query_servicenow()
        while len(data["result"]) > 0:
            logging.debug(
                "Returned %s Records, current offset is: %s",
                len(data["result"]),
                self.offset,
            )
            for issue in data["result"]:
                logging.info(
                    "Found issue opened: %s, %s: %s",
                    issue.get("number"),
                    issue.get(SN_OPENED_FIELD),
                    issue.get(SN_RESOLVED_FIELD),
                )
                # Create the FailureMetric
                created_ts = parse_assuming_utc(
                    issue[SN_OPENED_FIELD], _DATETIME_FORMAT
                )
                created_ts = second_precision(created_ts).timestamp()
                resolution_ts = None
                if issue[SN_RESOLVED_FIELD]:
                    logging.info(
                        "Found issue close: %s, %s: %s",
                        issue.get(SN_RESOLVED_FIELD),
                        issue.get("number"),
                        issue.get(SN_OPENED_FIELD),
                    )
                    resolution_ts = parse_assuming_utc(
                        issue.get(SN_RESOLVED_FIELD), _DATETIME_FORMAT
                    )
                    resolution_ts = second_precision(resolution_ts).timestamp()

                tracker_issue = TrackerIssue(
                    issue.get("number"),
                    created_ts,
                    resolution_ts,
                    self.get_app_name(issue),
                )
                critical_issues.append(tracker_issue)
            data = self.query_servicenow()
        return critical_issues

    def query_servicenow(self):
        self.tracker_query = SN_QUERY.format(
            SN_OPENED_FIELD,
            SN_RESOLVED_FIELD,
            self.app_name_field,
            PAGE_SIZE,
            self.offset,
        )
        tracker_url = self.server + self.tracker_query

        # Do the HTTP request
        response = self.session.get(tracker_url)
        # Check for HTTP codes other than 200

        if response.status_code != 200:
            logging.error(
                "Status:, %s, Headers:, %s, Error Response: %s",
                response.status_code,
                response.headers,
                response.json(),
            )
            raise RuntimeError("Error connecting to Service now")
        # Decode the JSON response into a dictionary and use the data
        data = response.json()
        logging.debug(data.get("result"))
        self.offset = self.offset + PAGE_SIZE
        return data

    def get_app_name(self, issue):
        if issue.get(self.app_name_field):
            app_label = issue.get(self.app_name_field)
            return app_label
        return pelorus.DEFAULT_TRACKER_APP_LABEL

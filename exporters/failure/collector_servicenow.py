import logging
import re
from urllib.parse import urlparse

import requests
from attrs import converters, define, field

import pelorus
from failure.collector_base import AbstractFailureCollector, TrackerIssue, _issue_parse_failures
from pelorus.config import env_var_names, env_vars
from pelorus.config.log import REDACT, log
from pelorus.timeutil import parse_assuming_utc, second_precision
from pelorus.utils import set_up_requests_session

SN_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
SN_QUERY = (
    "/api/now/table/incident?sysparm_fields={0}%2C{1}%2Cstate%2Cnumber%2C{2}"
    "&sysparm_display_value=true&sysparm_limit={3}&sysparm_offset={4}"
)
SN_OPENED_FIELD = "opened_at"
SN_RESOLVED_FIELD = "resolved_at"

_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

PAGE_SIZE = 100

_SAFE_FIELD_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.]*$")


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

    tls_verify: bool = field(default=True, converter=converters.to_bool)
    session: requests.Session = field(factory=requests.Session, init=False)

    def __attrs_post_init__(self):
        parsed = urlparse(self.server)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"SERVER must use http or https scheme, got: {parsed.scheme!r}")
        if not parsed.hostname:
            raise ValueError("SERVER must include a hostname")
        if not _SAFE_FIELD_NAME.match(self.app_name_field):
            raise ValueError(f"Invalid APP_FIELD value: {self.app_name_field!r}")
        set_up_requests_session(
            self.session, self.tls_verify, username=self.username, token=self.token
        )
        self.session.headers.update(SN_HEADERS)

    def search_issues(self):
        critical_issues = []
        offset = 0
        data = self._query_servicenow(offset)
        skipped = 0
        while len(data["result"]) > 0:
            offset += PAGE_SIZE
            logging.debug(
                "Returned %s Records, current offset is: %s",
                len(data["result"]),
                offset,
            )
            for issue in data["result"]:
                try:
                    logging.debug(
                        "Found issue opened: %s, %s: %s",
                        issue.get("number"),
                        issue.get(SN_OPENED_FIELD),
                        issue.get(SN_RESOLVED_FIELD),
                    )
                    created_ts = parse_assuming_utc(
                        issue[SN_OPENED_FIELD], _DATETIME_FORMAT
                    )
                    created_ts = second_precision(created_ts).timestamp()
                    resolution_ts = None
                    if issue[SN_RESOLVED_FIELD]:
                        logging.debug(
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
                except Exception:
                    skipped += 1
                    _issue_parse_failures.inc()
                    logging.error(
                        "Failed to parse ServiceNow issue %s, skipping",
                        issue.get("number", "unknown"),
                        exc_info=True,
                    )
            data = self._query_servicenow(offset)
        if skipped:
            logging.warning("Skipped %d unparseable ServiceNow issues", skipped)
        logging.info("Found %d issues from ServiceNow", len(critical_issues))
        return critical_issues

    def _query_servicenow(self, offset: int):
        tracker_query = SN_QUERY.format(
            SN_OPENED_FIELD,
            SN_RESOLVED_FIELD,
            self.app_name_field,
            PAGE_SIZE,
            offset,
        )
        tracker_url = self.server + tracker_query

        response = self.session.get(tracker_url, timeout=30)
        if response.status_code != 200:
            logging.error(
                "ServiceNow request failed with status: %s, url: %s",
                response.status_code,
                tracker_url,
            )
            raise RuntimeError(f"Error connecting to ServiceNow (HTTP {response.status_code})")
        try:
            data = response.json()
        except requests.JSONDecodeError as exc:
            logging.error(
                "Invalid JSON response from ServiceNow, url: %s",
                tracker_url,
                exc_info=True,
            )
            raise RuntimeError("ServiceNow returned non-JSON response") from exc
        if "result" not in data:
            logging.error(
                "ServiceNow response missing 'result' key, url: %s, keys: %s",
                tracker_url,
                list(data.keys()),
            )
            raise RuntimeError("ServiceNow response missing 'result' key")
        logging.debug("ServiceNow query result: %s", data.get("result"))
        return data

    def get_app_name(self, issue):
        return issue.get(self.app_name_field) or pelorus.DEFAULT_TRACKER_APP_LABEL

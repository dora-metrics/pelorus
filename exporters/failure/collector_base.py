from __future__ import annotations

import logging
import time
from abc import abstractmethod
from typing import Collection, Iterable

from prometheus_client import Counter, Gauge
from prometheus_client.core import GaugeMetricFamily

import pelorus
from provider_common import format_app_name


_collection_duration = Gauge(
    "pelorus_failure_collection_duration_seconds",
    "Duration of the last failure metric collection in seconds",
)
_collection_errors = Counter(
    "pelorus_failure_collection_errors_total",
    "Total number of failure metric collection errors",
)
_last_collection_count = Gauge(
    "pelorus_failure_last_collection_count",
    "Number of metrics returned by the last failure collection",
)
_issue_parse_failures = Counter(
    "pelorus_failure_issue_parse_failures_total",
    "Total number of individual issue/incident parse failures",
)


class FailureProviderAuthenticationError(Exception):
    auth_message = "Check the TOKEN: not authorized, invalid credentials"

    def __init__(self, message=auth_message):
        super().__init__(message)


class AbstractFailureCollector(pelorus.AbstractPelorusExporter):
    """Base class for failure collectors that fetch issue data from different trackers."""

    _FAILURE_METRIC_LABELS = ["app", "issue_number"]

    @staticmethod
    def _new_creation_metric():
        return GaugeMetricFamily(
            "failure_creation_timestamp",
            "Failure Creation Timestamp",
            labels=AbstractFailureCollector._FAILURE_METRIC_LABELS,
        )

    @staticmethod
    def _new_resolution_metric():
        return GaugeMetricFamily(
            "failure_resolution_timestamp",
            "Failure Resolution Timestamp",
            labels=AbstractFailureCollector._FAILURE_METRIC_LABELS,
        )

    def describe(self) -> list[GaugeMetricFamily]:
        return [self._new_creation_metric(), self._new_resolution_metric()]

    def collect(self) -> Iterable[GaugeMetricFamily]:
        logging.debug("collect: start")
        start = time.monotonic()
        collected_count = 0
        try:
            creation_metric = self._new_creation_metric()
            failure_metric = self._new_resolution_metric()

            critical_issues = self.search_issues()
            logging.debug("Collected %d failure(s) in this run", len(critical_issues))

            if critical_issues:
                metrics = self.generate_metrics(critical_issues)
                for m in metrics:
                    collected_count += 1
                    if not m.is_resolution:
                        logging.debug(
                            "Collected failure_creation_timestamp{ app=%s, issue_number=%s } %s",
                            m.labels[0], m.labels[1], m.time_stamp,
                        )
                        creation_metric.add_metric(
                            [format_app_name(m.labels[0]), m.labels[1]],
                            m.time_stamp,
                            timestamp=m.time_stamp,
                        )
                    else:
                        logging.debug(
                            "Collected failure_resolution_timestamp{ app=%s, issue_number=%s } %s",
                            m.labels[0], m.labels[1], m.time_stamp,
                        )
                        failure_metric.add_metric(
                            [format_app_name(m.labels[0]), m.labels[1]],
                            m.time_stamp,
                            timestamp=m.time_stamp,
                        )

            yield creation_metric
            yield failure_metric
        except Exception:
            _collection_errors.inc()
            logging.error("Failure metric collection failed", exc_info=True)
            yield self._new_creation_metric()
            yield self._new_resolution_metric()
        finally:
            duration = time.monotonic() - start
            _collection_duration.set(duration)
            _last_collection_count.set(collected_count)
            logging.info("collect: %d metrics in %.2fs", collected_count, duration)

    def generate_metrics(
        self, issues: Iterable[TrackerIssue]
    ) -> Iterable[FailureMetric]:
        for issue in issues:
            yield FailureMetric(
                issue.creationdate, False, labels=[issue.app, issue.issue_number]
            )
            if issue.resolutiondate:
                yield FailureMetric(
                    issue.resolutiondate, True, labels=[issue.app, issue.issue_number]
                )

    @abstractmethod
    def search_issues(self) -> Collection[TrackerIssue]: ...


class TrackerIssue:
    __slots__ = ("issue_number", "creationdate", "resolutiondate", "app")

    def __init__(
        self,
        issue_number: str,
        creationdate: str | float | int,
        resolutiondate: str | float | int | None,
        app: str,
    ):
        self.creationdate = creationdate
        self.resolutiondate = resolutiondate
        self.issue_number = issue_number
        self.app = app


class FailureMetric:
    __slots__ = ("time_stamp", "is_resolution", "labels")

    def __init__(
        self, time_stamp: str | float | int, is_resolution=False, labels=None
    ):
        if labels is None:
            labels = []
        self.time_stamp = time_stamp
        self.is_resolution = is_resolution
        self.labels = labels


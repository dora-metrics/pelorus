from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Collection, Iterable, Union

from prometheus_client.core import GaugeMetricFamily

import pelorus
from provider_common import format_app_name

# TODO 1: CI needs to create failures on the fly to enable this
# from pelorus.timeutil import METRIC_TIMESTAMP_THRESHOLD_MINUTES, is_out_of_date


class AbstractFailureCollector(pelorus.AbstractPelorusExporter):
    """
    Base class for a FailureCollector.
    This class should be extended for the system which contains the failure records.
    """

    def collect(self):
        # This function runs when the app starts and every time the /metrics
        # endpoint is accessed
        creation_metric = GaugeMetricFamily(
            "failure_creation_timestamp",
            "Failure Creation Timestamp",
            labels=["app", "issue_number"],
        )
        failure_metric = GaugeMetricFamily(
            "failure_resolution_timestamp",
            "Failure Resolution Timestamp",
            labels=["app", "issue_number"],
        )

        critical_issues = self.search_issues()
        logging.debug(f"Collected {len(critical_issues)} failure(s) in this run")

        if critical_issues:
            metrics = self.generate_metrics(critical_issues)
            # TODO 1:
            # number_of_dropped = 0
            for m in metrics:
                # TBD_1:
                # if not is_out_of_date(str(m.deploy_time_timestamp)):
                if not m.is_resolution:
                    logging.debug(
                        "Collected failure_creation_timestamp{ app=%s, issue_number=%s } %s"
                        % (m.labels[0], m.labels[1], m.time_stamp)
                    )
                    creation_metric.add_metric(
                        [format_app_name(m.labels[0]), m.labels[1]],
                        m.get_value(),
                        timestamp=m.get_value(),
                    )
                else:
                    logging.debug(
                        "Collected failure_resolution_timestamp{ app=%s, issue_number=%s } %s"
                        % (m.labels[0], m.labels[1], m.time_stamp)
                    )
                    failure_metric.add_metric(
                        [format_app_name(m.labels[0]), m.labels[1]],
                        m.get_value(),
                        timestamp=m.get_value(),
                    )
            # TODO 1:
            #     else:
            #         number_of_dropped += 1
            #         debug_msg = f"Failure too old to be collected: failure_{'resolution' " \
            #                      "if m.is_resolution else 'creation'}_timestamp{{ app={m.labels[0]}, " \
            #                      "issue_number={m.labels[1]} }} {m.time_stamp}"
            #         logging.debug(debug_msg)
            # if number_of_dropped:
            #     logging.info(
            #         "Number of Failure metrics that are older then %smin and won't be collected: %s",
            #         METRIC_TIMESTAMP_THRESHOLD_MINUTES,
            #         number_of_dropped,
            #     )

            yield (creation_metric)
            yield (failure_metric)

    def generate_metrics(
        self, issues: Iterable[TrackerIssue]
    ) -> Iterable[FailureMetric]:
        metrics = []
        for issue in issues:
            # Create the FailureMetric
            metric = FailureMetric(
                issue.creationdate, False, labels=[issue.app, issue.issue_number]
            )
            metrics.append(metric)
            # If the issue has a resolution date, then
            if issue.resolutiondate:
                # Add the end metric
                metric = FailureMetric(
                    issue.resolutiondate, True, labels=[issue.app, issue.issue_number]
                )
                metrics.append(metric)
        return metrics

    @abstractmethod
    def search_issues(self) -> Collection[TrackerIssue]:
        # This will be tracker specific
        pass


class TrackerIssue:
    def __init__(
        self,
        issue_number,
        creationdate: Union[str, float, int],
        resolutiondate: Union[str, float, int],
        app,
    ):
        self.creationdate = creationdate
        self.resolutiondate = resolutiondate
        self.issue_number = issue_number
        self.app = app


class FailureMetric:
    def __init__(
        self, time_stamp: Union[str, float, int], is_resolution=False, labels=[]
    ):
        self.time_stamp = time_stamp
        self.is_resolution = is_resolution
        self.labels = labels

    def get_value(self):
        """Returns the timestamp"""
        return self.time_stamp

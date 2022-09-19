import logging
from abc import abstractmethod

from prometheus_client.core import GaugeMetricFamily

import pelorus


class AbstractFailureCollector(pelorus.AbstractPelorusExporter):
    """
    Base class for a FailureCollector.
    This class should be extended for the system which contains the failure records.
    """

    def __init__(self, server, user, apikey):
        """Constructor"""
        self.server = server
        self.user = user
        self.apikey = apikey

    def collect(self):
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

        if len(critical_issues) > 0:
            metrics = self.generate_metrics(critical_issues)
            for m in metrics:
                if not m.is_resolution:
                    logging.info(
                        "Collected failure_creation_timestamp{ app=%s, issue_number=%s } %s"
                        % (m.labels[0], m.labels[1], m.time_stamp)
                    )
                    creation_metric.add_metric(m.labels, m.get_value())
                else:
                    logging.info(
                        "Collected failure_resolution_timestamp{ app=%s, issue_number=%s } %s"
                        % (m.labels[0], m.labels[1], m.time_stamp)
                    )
                    failure_metric.add_metric(m.labels, m.get_value())
            yield (creation_metric)
            yield (failure_metric)

    def generate_metrics(self, issues):
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
    def search_issues(self):
        # This will be tracker specific
        pass

    @abstractmethod
    def convert_timestamp(self, date_time):
        # This will format timestamp based on tracker specific data
        pass


class TrackerIssue:
    def __init__(self, issue_number, creationdate, resolutiondate, app):
        self.creationdate = creationdate
        self.resolutiondate = resolutiondate
        self.issue_number = issue_number
        self.app = app


class FailureMetric:
    def __init__(self, time_stamp, is_resolution=False, labels=[]):
        self.time_stamp = time_stamp
        self.is_resolution = is_resolution
        self.labels = labels

    def get_value(self):
        """Returns the timestamp"""
        return self.time_stamp

from abc import abstractmethod
import pelorus
from prometheus_client.core import GaugeMetricFamily


class AbstractFailureCollector(pelorus.AbstractPelorusExporter):
    """
    Base class for a FailureCollector.
    This class should be extended for the system which contains the failure records.
    """

    def __init__(self, server, user, apikey, project):
        """Constructor"""
        self.server = server
        self.user = user
        self.apikey = apikey
        self.project = project

    def collect(self):
        creation_metric = GaugeMetricFamily('failure_creation_timestamp',
                                            'Failure Creation Timestamp',
                                            labels=['project', 'issue_number'])
        failure_metric = GaugeMetricFamily('failure_resolution_timestamp',
                                           'Failure Resolution Timestamp',
                                           labels=['project', 'issue_number'])

        critical_issues = self.search_issues()
        metrics = self.generate_metrics(self.project, critical_issues)

        if len(critical_issues) > 0:
            metrics = self.generate_metrics(self.project, critical_issues)
            for m in metrics:
                if not m.is_resolution:
                    creation_metric.add_metric(m.labels, m.get_value())
                    yield(creation_metric)
                else:
                    failure_metric.add_metric(m.labels, m.get_value())
                    yield(failure_metric)

    def generate_metrics(self, project, issues):
        metrics = []
        for issue in issues:
            # Create the FailureMetric
            metric = FailureMetric(issue.creationdate, False, labels=[project, issue.issue_number])
            metrics.append(metric)
            # If the issue has a resolution date, then
            if issue.resolutiondate:
                # Add the end metric
                metric = FailureMetric(issue.resolutiondate, True, labels=[project, issue.issue_number])
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


class TrackerIssue():
    def __init__(self, issue_number, creationdate, resolutiondate):
        self.creationdate = creationdate
        self.resolutiondate = resolutiondate
        self.issue_number = issue_number


class FailureMetric():
    def __init__(self, time_stamp, is_resolution=False, labels=[]):
        self.time_stamp = time_stamp
        self.is_resolution = is_resolution
        self.labels = labels

    def get_value(self):
        """Returns the timestamp"""
        return self.time_stamp

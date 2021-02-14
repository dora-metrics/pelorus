from abc import abstractmethod
import json
import logging
import pelorus
import re
from jsonpath_ng import parse
from prometheus_client.core import GaugeMetricFamily
import giturlparse


class AbstractCommitCollector(pelorus.AbstractPelorusExporter):
    """
    Base class for a CommitCollector.
    This class should be extended for the system which contains the commit information.
    """

    def __init__(self, username, token, collector_name, timedate_format, mongo_client, git_api=None, ):
        """Constructor"""
        self._username = username
        self._token = token
        self._git_api = git_api
        self._commit_dict = {}
        self._timedate_format = timedate_format
        self._collector_name = collector_name
        self._mongo_client = mongo_client
        logging.info("=====Using %s Collector=====" % (self._collector_name))

    def collect(self):
        print("collecting")
        commit_metric = GaugeMetricFamily('commit_timestamp',
                                          'Commit timestamp', labels=['app', 'commit', 'image_sha'])
        commit_metrics = self.generate_metrics()
        print(commit_metrics)
        for my_metric in commit_metrics:
            logging.info("Collected commit_timestamp{ app=%s, commit=%s, image_sha=%s } %s"
                         % (
                             my_metric.name,
                             my_metric.commit_hash,
                             my_metric.image_hash,
                             str(float(my_metric.commit_timestamp))
                         )
                         )
            commit_metric.add_metric([my_metric.name, my_metric.commit_hash, my_metric.image_hash],
                                     my_metric.commit_timestamp)
            yield commit_metric

    def generate_metrics(self):
        """Method called by the collect to create a list of metrics to publish"""
        # Initialize metrics list
        print("generating metrics")
        metrics = []

        for build in self._mongo_client.build.builds.find():
            print(build)
            metrics.append(self.get_metric_from_build(build['app'], build['commit'], build['image_sha'], build['repo'], build['branch']))

        print("metrics generated")
        print(metrics)
        return metrics

    @abstractmethod
    def get_commit_time(self, metric):
        # This will perform the API calls and parse out the necessary fields into metrics
        pass

    def get_metric_from_build(self, app, commit_sha, image_hash, repo_url, branch):
        try:

            metric = CommitMetric(app)
            metric.repo_url = repo_url
            metric.build_name = app
            metric.build_config_name = app
            metric.namespace = None
            labels = None
            metric.labels = None
            metric.commit_hash = commit_sha
            metric.name = app
            metric.commiter = None
            metric.image_location = None
            metric.image_hash = image_hash
            # Check the cache for the commit_time, if not call the API
            metric_ts = self._commit_dict.get(commit_sha)
            if metric_ts is None:
                logging.debug("sha: %s, commit_timestamp not found in cache, executing API call." % (commit_sha))
                metric = self.get_commit_time(metric)
                # If commit time is None, then we could not get the value from the API
                if metric.commit_time is None:
                    return None
                # Add the timestamp to the cache
                self._commit_dict[metric.commit_hash] = metric.commit_timestamp
            else:
                metric.commit_timestamp = self._commit_dict[commit_sha]
                logging.debug("Returning sha: %s, commit_timestamp: %s, from cache." % (
                    commit_sha, metric.commit_timestamp))

            return metric

        except Exception as e:
            logging.warning("Build %s/%s in app %s is missing required attributes to collect data. Skipping."
                            % (namespace, build.metadata.name, app))
            logging.debug(e, exc_info=True)
            return None


class CommitMetric:

    supported_protocols = ['http', 'https', 'ssh', 'git']

    def __init__(self, app_name):
        self.name = app_name
        self.labels = None
        self.__repo_url = None
        self.__repo_protocol = None
        self.__repo_fqdn = None
        self.__repo_group = None
        self.__repo_name = None
        self.__repo_project = None
        self.commiter = None
        self.commit_hash = None
        self.commit_time = None
        self.commit_timestamp = None
        self.build_name = None
        self.build_config_name = None
        self.image_location = None
        self.image_name = None
        self.image_tag = None
        self.image_hash = None

    @property
    def repo_url(self):
        return self.__repo_url

    @repo_url.setter
    def repo_url(self, value):
        self.__repo_url = value
        self.__parse_repourl()

    @property
    def repo_protocol(self):
        """Returns the Git server protocol"""
        return self.__repo_protocol

    @property
    def git_fqdn(self):
        """Returns the Git server FQDN"""
        return self.__repo_fqdn

    @property
    def repo_group(self):
        return self.__repo_group

    @property
    def repo_name(self):
        """Returns the Git repo name, example: myrepo.git"""
        return self.__repo_name

    @property
    def repo_project(self):
        """Returns the Git project name, this is normally the repo_name with '.git' parsed off the end."""
        return self.__repo_project

    @property
    def git_server(self):
        """Returns the Git server FQDN with the protocol"""
        return str(self.__repo_protocol + '://' + self.__repo_fqdn)

    def __parse_repourl(self):
        """Parse the repo_url into individual pieces"""
        if self.__repo_url is None:
            return
        parsed = giturlparse.parse(self.__repo_url)
        if len(parsed.protocols) > 0 and parsed.protocols[0] not in CommitMetric.supported_protocols:
            raise ValueError("Unsupported protocol %s", parsed.protocols[0])
        self.__repo_protocol = parsed.protocol
        # In the case of multiple subgroups the host will be in the pathname
        # Otherwise, it will be in the resource
        if parsed.pathname.startswith('//'):
            self.__repo_fqdn = parsed.pathname.split("/")[2]
            self.__repo_protocol = parsed.protocols[0]
        else:
            self.__repo_fqdn = parsed.resource
        self.__repo_group = parsed.owner
        self.__repo_name = parsed.name
        self.__repo_project = parsed.name
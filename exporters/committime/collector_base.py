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

    # def __init__(self, kube_client, username, token, namespaces, apps, collector_name, timedate_format, git_api=None):
    def __init__(self, kube_client, git_provider_info, exporter_opts):
        """Constructor"""
        self._kube_client = kube_client
        self._username = git_provider_info.username
        self._token = git_provider_info.token
        self._git_api = git_provider_info.git_api
        self._timedate_format = git_provider_info.timedate_format
        self._collector_name = git_provider_info.collector_name
        self._namespaces = exporter_opts.namespaces
        self._apps = exporter_opts.apps
        self._no_image_stream = exporter_opts.no_image_stream
        self._commit_dict = {}
        logging.info("=====Using %s Collector=====" % (self._collector_name))

    def collect(self):
        commit_metric = GaugeMetricFamily('commit_timestamp',
                                          'Commit timestamp', labels=['namespace', 'app', 'commit', 'image_sha'])
        commit_metrics = self.generate_metrics()
        for my_metric in commit_metrics:
            logging.info("Collected commit_timestamp{ namespace=%s, app=%s, commit=%s, image_sha=%s } %s"
                         % (
                             my_metric.namespace,
                             my_metric.name,
                             my_metric.commit_hash,
                             my_metric.image_hash,
                             str(float(my_metric.commit_timestamp))
                         )
                         )
            commit_metric.add_metric([my_metric.namespace, my_metric.name, my_metric.commit_hash, my_metric.image_hash],
                                     my_metric.commit_timestamp)
            yield commit_metric

    def generate_metrics(self):
        """Method called by the collect to create a list of metrics to publish"""
        # This will loop and look at OCP builds (calls get_git_commit_time)
        if not self._namespaces:
            logging.info("No namespaces specified, watching all namespaces")
            v1_namespaces = self._kube_client.resources.get(api_version='v1', kind='Namespace')
            self._namespaces = [namespace.metadata.name for namespace in v1_namespaces.get().items]
        else:
            logging.info("Watching namespaces: %s" % (self._namespaces))

        # Initialize metrics list
        metrics = []
        for namespace in self._namespaces:
            # Initialized variables
            builds = []
            apps = []
            builds_by_app = {}
            app_label = pelorus.get_app_label()
            logging.debug("Searching for builds with label: %s in namespace: %s" % (app_label, namespace))

            v1_builds = self._kube_client.resources.get(api_version='build.openshift.io/v1', kind='Build')
            # only use builds that have the app label
            builds = v1_builds.get(namespace=namespace, label_selector=app_label)

            # use a jsonpath expression to find all values for the app label
            jsonpath_str = "$['items'][*]['metadata']['labels']['" + str(app_label) + "']"
            jsonpath_expr = parse(jsonpath_str)

            found = jsonpath_expr.find(builds)

            apps = [match.value for match in found]

            if not apps:
                continue
            # remove duplicates
            apps = list(dict.fromkeys(apps))
            builds_by_app = {}

            for app in apps:
                builds_by_app[app] = list(filter(lambda b: b.metadata.labels[app_label] == app, builds.items))

            metrics += self.get_metrics_from_apps(builds_by_app, namespace)

        return metrics

    @abstractmethod
    def get_commit_time(self, metric):
        # This will perform the API calls and parse out the necessary fields into metrics
        pass

    # get_metrics_from_apps - expects a sorted array of build data sorted by app label
    def get_metrics_from_apps(self, apps, namespace):
        metrics = []
        for app in apps:

            builds = apps[app]
            jenkins_builds = list(filter(lambda b: b.spec.strategy.type == 'JenkinsPipeline', builds))
            code_builds = list(filter(lambda b: b.spec.strategy.type in ['Source', 'Binary', 'Docker'], builds))
            # assume for now that there will only be one repo/branch per app
            # For jenkins pipelines, we need to grab the repo data
            # then find associated s2i/docker builds from which to pull commit & image data
            repo_url = None
            if jenkins_builds:
                # we will default to the repo listed in '.spec.source.git'
                repo_url = jenkins_builds[0].spec.source.git.uri

                # however, in cases where the Jenkinsfile and source code are separate, we look for params
                git_repo_regex = re.compile(r"(\w+://)(.+@)*([\w\d\.]+)(:[\d]+){0,1}/*(.*)")
                for env in jenkins_builds[0].spec.strategy.jenkinsPipelineStrategy.env:
                    result = git_repo_regex.match(env.value)
                    if result:
                        repo_url = env.value

            for build in code_builds:
                try:
                    metric = self.get_metric_from_build(build, app, namespace, repo_url)
                except Exception:
                    logging.error("Cannot collect metrics from build: %s" % (build.metadata.name))

                if metric:
                    metrics.append(metric)
        return metrics

    def get_metric_from_build(self, build, app, namespace, repo_url):
        try:

            metric = CommitMetric(app)

            if build.spec.source.git:
                repo_url = build.spec.source.git.uri
            else:
                repo_url = self._get_repo_from_build_config(build)

            metric.repo_url = repo_url
            commit_sha = build.spec.revision.git.commit
            metric.build_name = build.metadata.name
            metric.build_config_name = build.metadata.labels.buildconfig
            metric.namespace = build.metadata.namespace
            labels = build.metadata.labels
            metric.labels = json.loads(str(labels).replace("\'", "\""))

            metric.commit_hash = commit_sha
            metric.name = app
            metric.committer = build.spec.revision.git.author.name
            metric.image_location = build.status.outputDockerImageReference
            if build.spec.output.to.kind == "DockerImage" and self._no_image_stream:
                metric.image_hash = commit_sha
            else:
                metric.image_hash = build.status.output.to.imageDigest
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

    def _get_repo_from_build_config(self, build):
        """
        Determines the repository url from the parent BuildConfig that created the Build resource in case
        the BuildConfig has the git uri but the Build does not
        :param build: the Build resource
        :return: repo_url as a str or None if not found
        """
        v1_build_configs = self._kube_client.resources.get(api_version='build.openshift.io/v1', kind='BuildConfig')
        build_config = v1_build_configs.get(namespace=build.status.config.namespace,
                                            name=build.status.config.name)
        if build_config:
            if build_config.spec.source.git:
                git_uri = str(build_config.spec.source.git.uri)
                if git_uri.endswith('.git'):
                    return git_uri
                else:
                    return git_uri + '.git'

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
        self.committer = None
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

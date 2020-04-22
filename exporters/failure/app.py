#!/usr/bin/python3
import os
import re
import time
import pytz
from datetime import datetime, timedelta, tzinfo
from abc import ABC, abstractmethod
from jira import JIRA
from jsonpath_ng import jsonpath, parse
from kubernetes import client
from lib_pelorus import loader
from openshift.dynamic import DynamicClient
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

loader.load_kube_config()
k8s_config = client.Configuration()
k8s_client = client.api_client.ApiClient(configuration=k8s_config)
dyn_client = DynamicClient(k8s_client)

class AbstractFailureCollector(ABC):
    """
    Base class for a FailureCollector.
    This class should be extended for the system which contains the failure records.
    """

    def __init__(self, server, user, apikey):
        """Constructor"""
        self.server = server
        self.user = user
        self.apikey = apikey

    @abstractmethod
    def collect(self):
        """Method called to collect data and send to Prometheus"""
        pass

    @abstractmethod
    def generate_metrics(self):
        """Method called by the collect to create a list of metrics to publish"""
        pass

class AbstractFailureMetric(ABC):
    def __init__(self, labels = []):
        self.labels = labels

class JiraFailureMetric(AbstractFailureMetric):
    def __init__(self, jira_project, issue_number, time_stamp, labels = []):
        super().__init__(labels)
        self.jira_project = jira_project
        self.issue_number = issue_number
        self.time_stamp = time_stamp
    
    def get_value(self):
        """Returns the timestamp"""
        return self.time_stamp


class JiraFailureCollector(AbstractFailureCollector):
    """
    Jira implementation of a FailureCollector
    """

    def __init__(self, server, user, apikey, project = 'MDT'):
        self.project = project
        super().__init__(server, user, apikey)

    def collect(self):
        print("Starting Collection")
        options = {
            'server': self.server
        }
        #Connect to Jira
        jira = JIRA(options, basic_auth=(self.user, self.apikey))
        # TODO FIXME This may need to be modified to suit needs and have a time period. 
        query_string = "project=" + self.project +  " and type=bug and priority=highest"
        #Query Jira and loop results if any are returned.
        critical_issues = jira.search_issues(query_string)
        if len(critical_issues) > 0:
            metric = GaugeMetricFamily('failure_timestamp', 'Failure timestamp', labels=['project', 'issue_number', 'issue_stage'])
            metrics = self.generate_metrics(self.project, critical_issues)
            for m in metrics:
                metric.add_metric(m.labels, m.get_value())
                yield(metric)
    

    def convert_jira_timestamp(self, date_time):
        """Convert a Jira datetime with TZ to UTC """
        #The time retunred by Jira has a TZ, so convert to UTC
        utc = datetime.strptime(date_time, '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(pytz.utc)
        #Change the datetime to a string
        utc_string = utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        #convert to timestamp
        return loader.convert_date_time_to_timestamp(utc_string)

    def generate_metrics(self, project, issues):
        metrics = []
        for issue in issues:
            print('Found open issue: {}, {}: {}'.format(str(issue.fields.created), issue.key, issue.fields.summary))
            #Create the JiraFailureMetric
            created_ts = self.convert_jira_timestamp(issue.fields.created)
            metric = JiraFailureMetric(project, issue.key, created_ts, labels= [project, issue.key, "issue_creation_timestamp"])
            metrics.append(metric)
            #If the issue has a resolution date, then 
            if issue.fields.resolutiondate:
                resolution_ts = self.convert_jira_timestamp(issue.fields.resolutiondate)
                #Add the end metric
                print('Found closed issue: {}, {}: {}'.format(str(issue.fields.resolutiondate), issue.key, issue.fields.summary))
                metric = JiraFailureMetric(project, issue.key, resolution_ts, labels = [project, issue.key, "issue_resolution_timestamp"])
                metrics.append(metric)
                #Add the change metric
                resolution_runtime = int(resolution_ts - created_ts)
                print('Issue Resolution Time (in seconds): {}, {}: {}'.format(str(resolution_runtime), issue.key, issue.fields.summary))
                metric = JiraFailureMetric(project, issue.key, resolution_runtime, labels = [project, issue.key, "issue_resolution_time_seconds"])
                metrics.append(metric)

        return metrics

if __name__ == "__main__":
    print("===== Starting Failure Collector =====")
    start_http_server(8080)
    project =  os.environ.get('PROJECT')
    user =  os.environ.get('USER')
    token =  os.environ.get('TOKEN')
    server =  os.environ.get('SERVER')
    print("Project: " + project)
    print("Server: " + server)
    print("User: " + user)
    REGISTRY.register(JiraFailureCollector(server, user, token, project))
    while True:
        time.sleep(1)
    print("===== Exit Failure Collector =====")

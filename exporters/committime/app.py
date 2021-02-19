#!/usr/bin/python3
from collector_bitbucket import BitbucketCommitCollector
from collector_gitlab import GitLabCommitCollector
from collector_github import GitHubCommitCollector
import os
import pelorus
import sys
import time
from kubernetes import client
from openshift.dynamic import DynamicClient
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY
from pymongo import MongoClient

REQUIRED_CONFIG = ['GIT_USER', 'GIT_TOKEN', 'PROVIDER']


class GitFactory:
    @staticmethod
    def getCollector(kube_client, username, token, namespaces, apps, git_api, git_provider, db):
        if git_provider == "gitlab":
            return GitLabCommitCollector(kube_client, username, token, namespaces, apps, db)
        if git_provider == "github":
            return GitHubCommitCollector(kube_client, username, token, namespaces, apps, git_api, db)
        if git_provider == "bitbucket":
            return BitbucketCommitCollector(kube_client, username, token, namespaces, apps, db)


if __name__ == "__main__":
    pelorus.upgrade_legacy_vars()
    if pelorus.missing_configs(REQUIRED_CONFIG):
        print("This program will exit.")
        sys.exit(1)

    pelorus.load_kube_config()
    k8s_config = client.Configuration()
    k8s_client = client.api_client.ApiClient(configuration=k8s_config)
    dyn_client = DynamicClient(k8s_client)

    db = None
    if os.environ.get('PROVIDER') == "webhook":
        if pelorus.missing_configs(['MONGODB_USER', 'MONGODB_PASSWORD', 'MONGODB_SERVICE_HOST', 'MONGODB_DATABASE']):
            print("Missing configs for Mongo; exiting...")
            sys.exit(1)

        mongo_username = os.environ.get('MONGODB_USER')
        mongo_password = os.environ.get('MONGODB_PASSWORD')
        mongo_servicename = os.environ.get('MONGODB_SERVICE_HOST')
        mongo_database = os.environ.get('MONGODB_DATABASE')
        uri = "mongodb://%s:%s@%s:27017/%s" % (mongo_username, mongo_password, mongo_servicename, mongo_database)
        db = MongoClient(uri)[mongo_database]

    username = os.environ.get('GIT_USER')
    token = os.environ.get('GIT_TOKEN')
    git_api = os.environ.get('GIT_API')
    git_provider = os.environ.get('GIT_PROVIDER', pelorus.DEFAULT_GIT)
    namespaces = None
    if os.environ.get('NAMESPACES') is not None:
        namespaces = [proj.strip() for proj in os.environ.get('NAMESPACES').split(",")]
    apps = None
    start_http_server(8080)

    collector = GitFactory.getCollector(dyn_client, username, token, namespaces, apps, git_api, git_provider, db)
    REGISTRY.register(collector)

    while True:
        time.sleep(1)

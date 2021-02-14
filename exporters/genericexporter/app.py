#!/usr/bin/python3
# from collector_bitbucket import BitbucketCommitCollector
# from collector_gitlab import GitLabCommitCollector
from collector_github import GitHubCommitCollector
import os
import pelorus
import sys
import time
from prometheus_client.core import REGISTRY
from prometheus_client import start_http_server
from pymongo import MongoClient

REQUIRED_CONFIG = ['MONGODB_USER', 'MONGODB_PASSWORD', 'MONGODB_SERVICE_HOST', 'MONGODB_DATABASE', 'GIT_USER', 'GIT_TOKEN']

class GitFactory:
    @staticmethod
    def getCollector(username, token, git_api, git_provider, db):
        if git_provider == "gitlab":
            pass
        if git_provider == "github":
            return GitHubCommitCollector(username, token, db, git_api)
        if git_provider == "bitbucket":
            pass

if __name__ == "__main__":
    print("starting app")

    if pelorus.missing_configs(REQUIRED_CONFIG):
        print("This program will exit.")
        sys.exit(1)

    mongo_username = os.environ.get('MONGODB_USER')
    mongo_password = os.environ.get('MONGODB_PASSWORD')
    mongo_servicename = os.environ.get('MONGODB_SERVICE_HOST')
    mongo_database = os.environ.get('MONGODB_DATABASE')
    uri = "mongodb://%s:%s@%s:27017/%s" % (mongo_username,mongo_password,mongo_servicename,mongo_database)
    db = MongoClient(uri)[mongo_database]

    username = os.environ.get('GIT_USER')
    token = os.environ.get('GIT_TOKEN')
    git_api = os.environ.get('GIT_API')
    git_provider = os.environ.get('GIT_PROVIDER', pelorus.DEFAULT_GIT)

    collector = GitFactory.getCollector(username, token, git_api, git_provider, db)
    REGISTRY.register(collector)

    start_http_server(8080)

    while True:
        time.sleep(1)
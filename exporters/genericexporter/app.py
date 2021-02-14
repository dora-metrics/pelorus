#!/usr/bin/python3
from collector_bitbucket import BitbucketCommitCollector
from collector_gitlab import GitLabCommitCollector
from collector_github import GitHubCommitCollector
import os
import pelorus
import sys
import time
from prometheus_client.core import REGISTRY
# from prometheus_client import make_wsgi_app
from prometheus_client import start_http_server
from pymongo import MongoClient

# app = make_wsgi_app()
# print(__name__)

REQUIRED_CONFIG = ['MONGODB_USER', 'MONGODB_PASSWORD', 'GIT_USER', 'GIT_TOKEN']

class GitFactory:
    @staticmethod
    def getCollector(username, token, git_api, git_provider, mongo_client):
        if git_provider == "gitlab":
            return GitLabCommitCollector(username, token, git_api, mongo_client)
        if git_provider == "github":
            return GitHubCommitCollector(username, token, mongo_client, git_api)
        if git_provider == "bitbucket":
            return BitbucketCommitCollector(username, token, git_api, mongo_client)

if __name__ == "__main__":
    print("starting app")

    if pelorus.missing_configs(REQUIRED_CONFIG):
        print("This program will exit.")
        sys.exit(1)

    mongo_username = os.environ.get('MONGODB_USER')
    mongo_password = os.environ.get('MONGODB_PASSWORD')
    mongo_database = 'build'
    uri = "mongodb://%s:%s@mongodb:27017/%s" % (mongo_username,mongo_password,mongo_database)
    mongo_client = MongoClient(uri)

    username = os.environ.get('GIT_USER')
    token = os.environ.get('GIT_TOKEN')
    git_api = os.environ.get('GIT_API')
    git_provider = os.environ.get('GIT_PROVIDER', pelorus.DEFAULT_GIT)

    collector = GitFactory.getCollector(username, token, git_api, git_provider, mongo_client)
    REGISTRY.register(collector)

    start_http_server(8080)

    while True:
        time.sleep(1)
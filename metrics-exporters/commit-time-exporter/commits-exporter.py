import os
import json
import time
import requests
from datetime import datetime
from prometheus_client import start_http_server
from prometheus_client.core import CounterMetricFamily,InfoMetricFamily,GaugeMetricFamily, REGISTRY

class CommitCollector(object):
    _prefix = "https://api.github.com/repos/"
    _suffix = "/commits"
    def __init__(self, username, token, repos):
        self._username = username
        self._token = token
        self._repos = repos
        self._urls = generate_urls(repos)
    def collect(self):
        metric = GaugeMetricFamily('github_commit_timestamp', 'Commit timestamp', labels=['repo', 'commit_hash'])
        for repo in self._repos:
            url = self._prefix + repo.strip() + self._suffix
            print(url)
            response = requests.get(url, auth=(self._username, self._token))
            result = response.json()
            for commit in result:
                print(commit)
                message = commit['commit']['message']
                commit_hash = commit['sha']
                print(message)
                time = commit['commit']['committer']['date']
                unixformattime = convert_date_time_to_timestamp(time)
                print(unixformattime)
                metric.add_metric([repo, commit_hash], unixformattime)
            yield metric

def convert_date_time_to_timestamp(date_time):
    timestamp = datetime.strptime(date_time, '%Y-%m-%dT%H:%M:%SZ')
    unixformattime = (timestamp - datetime(1970, 1, 1)).total_seconds()
    return unixformattime

def generate_urls(repos):
    prefix = "https://api.github.com/repos/"
    suffix = "/commits"
    repos_urls = [ prefix+repo.strip()+suffix for repo in repos ]
    return repos_urls


if __name__ == "__main__":
    username = os.environ.get('GITHUB_USER')
    token = os.environ.get('GITHUB_TOKEN')
    repos = os.environ.get('GITHUB_REPOS').split(',')
    REGISTRY.register(CommitCollector(username, token, repos))
    start_http_server(9118)
    while True: time.sleep(1)


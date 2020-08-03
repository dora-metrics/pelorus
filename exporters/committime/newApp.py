#!/usr/bin/python3
from abc import ABC, abstractmethod


class AbstractPelorusExporter(ABC):
    """
    Base class for PelorusExporter
    """
    def __init_():
        pass

"""
Will hold info about repository (username, token, etc)
"""
class GenericRepository():


class AbstractCommitCollector(AbstractPelorusExporter):
    """
    Base class for a CommitCollector.
    This class should be extended for the system which contains the commit information.
    """

    def __init__(self, username, token, namespaces, apps, git_api=None):
        """Constructor"""
        self._username = username
        self._token = token
        self._namespaces = namespaces
        self._apps = apps
        self._git_api = git_api

    def collect(self):
        """Method called to collect data and send to Prometheus"""
        pass

    def generate_metrics(self):
        """Method called by the collect to create a list of metrics to publish"""
        # This will loop and look at OCP builds (calls get_git_commit_time)
        pass

    @abstractmethod
    def get_commit_time(self):
        # This will perform the API calls and parse out the necessary fields into metrics
        pass


class CommitMetric():
    def __init__(self, labels=None):
        super().__init__(labels)
        # todo add metrics values


class GitLabCommitCollector(AbstractCommitCollector):

    def __init__(self, username, token, namespaces, apps):
        super().__init__(username, token, namespaces, apps)

    def get_commit_time(self):
        """Method called to collect data and send to Prometheus"""
        print("GitLab")


class GitHubCommitCollector(AbstractCommitCollector):

    def __init__(self, username, token, namespaces, apps):
        super().__init__(username, token, namespaces, apps)

    def get_commit_time(self):
        """Method called to collect data and send to Prometheus"""
        print("GitHub")


class BitbucketCommitCollector(AbstractCommitCollector):

    def __init__(self, username, token, namespaces, apps):
        super().__init__(username, token, namespaces, apps)

    def get_commit_time(self):
        """Method called to collect data and send to Prometheus"""
        print("BitBucket")


class GitFactory:
    @staticmethod
    def getCollector(type):
        if type == "gitlab":
            return GitLabCommitCollector("", "", "", "")
        if type == "github":
            return GitHubCommitCollector("", "", "", "")
        if type == "bitbucket":
            return BitbucketCommitCollector("", "", "", "")


if __name__ == "__main__":

    for git_type in ("github", "gitlab", "bitbucket"):
        collector = GitFactory.getCollector(git_type)
        collector.get_commit_time()

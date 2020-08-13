from collector_base import AbstractCommitCollector


class GitLabCommitCollector(AbstractCommitCollector):

    def __init__(self, username, token, namespaces, apps):
        super().__init__(username, token, namespaces, apps)

    def get_commit_time(self):
        """Method called to collect data and send to Prometheus"""
        print("GitLab")

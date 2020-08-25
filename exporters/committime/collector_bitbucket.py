from collector_base import AbstractCommitCollector


class BitbucketCommitCollector(AbstractCommitCollector):

    def __init__(self, username, token, namespaces, apps):
        super().__init__(username, token, namespaces, apps, "BitBucket", "TODO-DateFormat")

    def get_commit_time(self, metric):
        """Method called to collect data and send to Prometheus"""
        print("BitBucket is not yet supported")

import requests
import json
import logging
import pelorus
from collector_base import AbstractCommitCollector
import urllib3
urllib3.disable_warnings()


class BitbucketCommitCollector(AbstractCommitCollector):

    # globals for Bitbucket v1 API
    V1_API_ROOT = 'rest/api'
    V1_API_TEST = '1.0/projects'
    V1_API_PATTERN = '1.0/projects/{group}/repos/{project}/commits/{commit}'
    # globals for Bitbucket v2 API
    V2_API_ROOT = 'api'
    V2_API_TEST = '2.0/repositories'
    V2_API_PATTERN = '2.0/repositories/{group}/{project}/commit/{commit}'
    # Default http headers needed for API calls
    DEFAULT_HEADERS = {'Content-Type': 'application/json', 'Accept': 'application/json'}

    def __init__(self, kube_client, username, token, namespaces, apps):
        super().__init__(kube_client, username, token, namespaces, apps, 'BitBucket', '%Y-%m-%dT%H:%M:%S%z')
        self.__server_dict = {}
        self.__session = requests.Session()

    # base class impl
    def get_commit_time(self, metric):
        """Method called to collect data and send to Prometheus"""

        git_server = metric.git_server
        # do a simple check for hosted Git services.
        if "github" in git_server or "gitlab" in git_server:
            logging.warn("Skipping non BitBucket server, found %s" % (git_server))
            return None

        # Set the session auth
        self.__session.auth = (self._username, self._token)

        # Get or figure out the BB API version
        # check the cache
        api_version = self.__server_dict.get(git_server)
        if api_version is None:
            # cache miss, figure out the api
            # try version 2.0
            if self.get_api_verison(self.__session, git_server, self.V2_API_ROOT, self.V2_API_TEST):
                self.__server_dict[git_server] = '2.0'
                api_version = self.__server_dict.get(git_server)
            else:  # try version 1.0
                if self.get_api_verison(self.__session, git_server, self.V1_API_ROOT, self.V1_API_TEST):
                    self.__server_dict[git_server] = '1.0'
                    api_version = self.__server_dict.get(git_server)
                else:
                    logging.error("Unable to determine API version for Bitbucket server: %s" % (git_server))
                    return metric

        # get the project, group and commit sha properties from the existing metric
        project_name = metric.repo_project
        sha = metric.commit_hash
        group = metric.repo_group

        # set API variables depending on the version
        if api_version == '1.0':
            api_root = self.V1_API_ROOT
            api_pattern = self.V1_API_PATTERN
            # Due to the BB V1 git pattern differences, need remove '/scm' and parse again.
            old_url = metric.repo_url
            # Parse out the V1 /scm, for whatever reason why it is present.
            new_url = old_url.replace('/scm', '')
            metric.repo_url = new_url
            # set the new project name
            project_name = metric.repo_project
            # set the new group
            group = metric.repo_group
            # set the URL back to the original
            metric.repo_url = old_url
        elif api_version == '2.0':
            api_root = self.V2_API_ROOT
            api_pattern = self.V2_API_PATTERN

        # Create the API server from the Git server and API Root
        api_server = pelorus.url_joiner(git_server, api_root)

        # Finally, make the API call
        api_response = None
        try:
            path = api_pattern.format(group=group, project=project_name, commit=sha)
            url = pelorus.url_joiner(api_server, path)
            response = self.__session.request("GET", url=url, headers=self.DEFAULT_HEADERS)
            response.encoding = 'utf-8'
            api_response = response
        except Exception:
            logging.warning("Failed to find project: %s, repo: %s for build %s" % (
                metric.repo_url, project_name, metric.build_name), exc_info=True)
            return metric

        # Check for a valid response and continue if none is found
        if api_response is None or api_response.status_code != 200 or api_response.text is None:
            logging.warning("Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s" % (
                metric.build_name, metric.commit_hash, metric.repo_fqdn, str(response.status_code)))
            return metric
        try:
            logging.debug("API call returned: %s" % (api_response.text))
            api_j = json.loads(response.text)
            if api_version == '2.0':
                # API V2 only has the commit time, which needs to be converted.
                # get the commit date/time
                commit_time = api_j["date"]
                logging.debug("API returned sha: %s, commit date: %s" % (sha, str(commit_time)))
                # set the commit time from the API
                metric.commit_time = commit_time
                # set the timestamp after conversion
                metric.commit_timestamp = pelorus.convert_date_time_to_timestamp(
                    metric.commit_time, self._timedate_format)
            else:
                # API V1 has the commit timestamp, which does not need to be converted
                commit_timestamp = api_j["committerTimestamp"]
                metric.commit_timestamp = commit_timestamp
        except Exception:
            logging.error("Failed processing commit time for build %s" % metric.build_name, exc_info=True)
            raise
        return metric

    def get_api_verison(self, session, git_server, api_root, api_test):
        try:
            api_server = pelorus.url_joiner(git_server, api_root)
            url = pelorus.url_joiner(api_server, api_test)
            response = session.request("GET", url=url, headers=self.DEFAULT_HEADERS)
            if response.status_code == 200:
                return True
        except Exception:
            return False

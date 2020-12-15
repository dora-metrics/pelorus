import requests
import json
import logging
import pelorus
from collector_base import AbstractCommitCollector
# import urllib3
# urllib3.disable_warnings()


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
        api_version = self.get_api_version(git_server)
        if api_version is None:
            return metric

        # get the project, group, and commit sha properties from the existing metric
        project_name = metric.repo_project
        sha = metric.commit_hash
        group = metric.repo_group

        try:
            # set API variables depending on the version
            if api_version == '1.0':
                # start with the V1 globals
                api_root = self.V1_API_ROOT
                api_pattern = self.V1_API_PATTERN
                # Due to the BB V1 git pattern differences, need remove '/scm' and parse again.
                old_url = metric.repo_url
                # Parse out the V1 /scm, for whatever reason why it is present.
                new_url = old_url.replace('/scm', '')
                # set the new url, so the parsing will happen
                metric.repo_url = new_url
                # set the new project name
                project_name = metric.repo_project
                # set the new group
                group = metric.repo_group
                # set the URL back to the original
                metric.repo_url = old_url
            elif api_version == '2.0':
                # Just set the V2 globals
                api_root = self.V2_API_ROOT
                api_pattern = self.V2_API_PATTERN

            # Create the API server from the Git server and API Root
            api_server = pelorus.url_joiner(git_server, api_root)

            # Finally, make the API call
            api_response = self.get_commit_information(api_pattern, api_server, group, project_name, sha, metric)

            # Check for a valid response and continue if none is found
            if api_response is None or api_response.status_code != 200 or api_response.text is None:
                logging.warning("Unable to retrieve commit time for build: %s, hash: %s, url: %s. Got http code: %s" % (
                    metric.build_name, metric.commit_hash, metric.repo_fqdn, str(api_response.status_code)))
                return metric

            logging.debug("API call returned: %s" % (api_response.text))
            api_j = json.loads(api_response.text)
            if api_version == '2.0':
                # API V2 only has the commit time, which needs to be converted.
                # get the commit date/time
                commit_time = api_j["date"]
                logging.debug("API v2 returned sha: %s, commit date: %s" % (sha, str(commit_time)))
                # set the commit time from the API
                metric.commit_time = commit_time
                # set the timestamp after conversion
                metric.commit_timestamp = pelorus.convert_date_time_to_timestamp(
                    metric.commit_time, self._timedate_format)
            else:
                # API V1 has the commit timestamp, which does not need to be converted
                commit_timestamp = api_j["committerTimestamp"]
                logging.debug("API v1 returned sha: %s, timestamp: %s" % (sha, str(commit_timestamp)))
                # Convert timestamp from miliseconds to seconds
                converted_timestamp = commit_timestamp / 1000
                # set the timestamp in the metric
                metric.commit_timestamp = converted_timestamp
                # convert the time stamp to datetime and set in metric
                metric.commit_time = pelorus.convert_timestamp_to_date_time_str(converted_timestamp)
        except Exception:
            logging.error("Failed processing commit time for build %s" % metric.build_name, exc_info=True)
            raise
        return metric

    def get_commit_information(self, api_pattern, api_server, group, project_name, sha, metric):
        """Makes an API call to get the commit information"""
        # Finally, make the API call
        api_response = None
        try:
            # build the API path using, group, project and commit sha
            path = api_pattern.format(group=group, project=project_name, commit=sha)
            # create the full URL
            url = pelorus.url_joiner(api_server, path)
            # send a GET
            response = self.__session.request("GET", url=url, headers=self.DEFAULT_HEADERS)
            response.encoding = 'utf-8'
            api_response = response
        except Exception:
            logging.warning("Failed to find project: %s, repo: %s for build %s" % (
                metric.repo_url, project_name, metric.build_name), exc_info=True)
        return api_response

    def get_api_version(self, git_server):
        """Checks the map for a the Git server API version.  If not found it makes an API call to determine."""
        api_version = self.__server_dict.get(git_server)
        if api_version is None:
            # cache miss, figure out the api
            # try version 2.0
            if self.check_api_verison(self.__session, git_server, self.V2_API_ROOT, self.V2_API_TEST):
                self.__server_dict[git_server] = '2.0'
                api_version = self.__server_dict.get(git_server)
            else:  # try version 1.0
                if self.check_api_verison(self.__session, git_server, self.V1_API_ROOT, self.V1_API_TEST):
                    self.__server_dict[git_server] = '1.0'
                    api_version = self.__server_dict.get(git_server)
        return api_version

    def check_api_verison(self, session, git_server, api_root, api_test):
        """Makes an API call to determine the API version"""
        try:
            api_server = pelorus.url_joiner(git_server, api_root)
            url = pelorus.url_joiner(api_server, api_test)
            response = session.request("GET", url=url, headers=self.DEFAULT_HEADERS)
            status_code = response.status_code
            if status_code == 200:
                return True
            else:
                logging.warning("Unable to retrieve API version for URL: %s . Got http code: %s" % (
                    url, str(status_code)))
                return False
        except Exception:
            return False

# Copyright Red Hat
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

import logging
from typing import List

from attrs import converters, define, field
from azure.devops.connection import Connection
from azure.devops.exceptions import AzureDevOpsServiceError
from azure.devops.v6_0.work_item_tracking.models import Wiql, WorkItem
from azure.devops.v6_0.work_item_tracking.work_item_tracking_client import (
    WorkItemTrackingClient,
)
from msrest.authentication import BasicAuthentication

from failure.collector_base import AbstractFailureCollector, TrackerIssue
from pelorus.config import env_var_names, env_vars
from pelorus.config.converters import comma_or_whitespace_separated, pass_through
from pelorus.config.log import REDACT, log
from pelorus.errors import FailureProviderAuthenticationError
from pelorus.timeutil import parse_assuming_utc_with_fallback, second_precision
from pelorus.utils import Url

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
_DATETIME_FORMAT_FALLBACK = "%Y-%m-%dT%H:%M:%SZ"


@define(kw_only=True)
class AzureDevOpsFailureCollector(AbstractFailureCollector):
    """
    Azure DevOps implementation of a FailureCollector
    """

    token: str = field(
        metadata=env_vars(*env_var_names.TOKEN) | log(REDACT),
        repr=False,
    )

    tracker_api: Url = field(
        metadata=env_vars("SERVER"),
        converter=converters.optional(pass_through(Url, Url.parse)),
    )

    projects: set[str] = field(
        factory=set, converter=comma_or_whitespace_separated(set)
    )

    work_item_type: set[str] = field(
        factory=set,
        converter=comma_or_whitespace_separated(set),
        metadata=env_vars("AZURE_DEVOPS_TYPE"),
    )

    work_item_priority: set[str] = field(
        factory=set,
        converter=comma_or_whitespace_separated(set),
        metadata=env_vars("AZURE_DEVOPS_PRIORITY"),
    )

    def __attrs_post_init__(self):
        try:
            credentials = BasicAuthentication("", self.token)
            connection = Connection(base_url=self.tracker_api.url, creds=credentials)
            self.client: WorkItemTrackingClient = (
                connection.clients_v6_0.get_work_item_tracking_client()
            )
        except AzureDevOpsServiceError as error:
            if error.type_key == "UnauthorizedRequestException":
                logging.error(FailureProviderAuthenticationError.auth_message)
                raise FailureProviderAuthenticationError from error
            logging.error(error.message)
            raise error

    def get_work_items(self) -> List[WorkItem]:
        logging.debug("Collecting work items")

        try:
            query_string = "Select [System.Id] From WorkItems"
            if self.work_item_type or self.work_item_priority:
                query_filters = []
                if self.work_item_type:
                    query_type = "', '".join(self.work_item_type)
                    query_filters.append(f"[System.WorkItemType] In ('{query_type}')")
                if self.work_item_priority:
                    query_priority = "', '".join(self.work_item_priority)
                    query_filters.append(
                        f"[Microsoft.VSTS.Common.Priority] In ('{query_priority}')"
                    )
                query_string += f" Where {' AND '.join(query_filters)}"

            wiql = Wiql(query=query_string)
            wiql_results = self.client.query_by_wiql(wiql).work_items
            chunk_size = 200
            wiql_chunk_results = [
                wiql_results[index : index + chunk_size]  # noqa
                for index in range(0, len(wiql_results), chunk_size)
            ]
            return [
                work_item
                for chunk in wiql_chunk_results
                for work_item in self.client.get_work_items(
                    ids=[str(result.id) for result in chunk],
                    fields=[
                        "System.Title",
                        "System.WorkItemType",
                        "System.CreatedDate",
                        "System.TeamProject",
                        "System.Tags",
                        "Microsoft.VSTS.Common.ClosedDate",
                        "Microsoft.VSTS.Common.Priority",
                    ],
                )
            ]
        except AzureDevOpsServiceError as error:
            if error.type_key == "UnauthorizedRequestException":
                logging.error(FailureProviderAuthenticationError.auth_message)
                raise FailureProviderAuthenticationError from error
            logging.error(error.message)
            raise error
        except Exception as error:
            logging.error(error)  # pragma: no cover
            raise  # pragma: no cover

    def filter_by_project(self, project: str) -> bool:
        if not self.projects:
            return True
        return project in self.projects

    def get_app_name(self, work_item: WorkItem) -> str:
        try:
            labels: str = work_item.fields["System.Tags"]
            labels = labels.split("; ")

            label_text = self.app_label + "="

            for label in labels:
                if label_text in label:
                    return label.replace(label_text, "")
            return "unknown"
        except KeyError:
            return "unknown"

    def search_issues(self) -> list[TrackerIssue]:
        """
        To maintain consistency, we call this method `search_issues`. An
        `issue` in Azure DevOps is called `work item`.
        """
        production_work_items = []
        for work_item in self.get_work_items():
            if self.filter_by_project(work_item.fields["System.TeamProject"]):
                created_at = work_item.fields["System.CreatedDate"]
                work_item_id = work_item.id
                title = work_item.fields["System.Title"]

                created_tz = parse_assuming_utc_with_fallback(
                    created_at, _DATETIME_FORMAT, _DATETIME_FORMAT_FALLBACK
                )
                created_ts = second_precision(created_tz).timestamp()

                try:
                    resolved_at = work_item.fields["Microsoft.VSTS.Common.ClosedDate"]
                    resolution_tz = parse_assuming_utc_with_fallback(
                        resolved_at, _DATETIME_FORMAT, _DATETIME_FORMAT_FALLBACK
                    )
                    resolution_ts = second_precision(resolution_tz).timestamp()

                    logging.debug(
                        "Found production incident closed: {}, {}: {}".format(
                            resolved_at,
                            work_item_id,
                            title,
                        )
                    )
                except KeyError:
                    logging.debug(
                        "Found production incident opened: {}, {}: {}".format(
                            created_at,
                            work_item_id,
                            title,
                        )
                    )
                    resolution_ts = None

                tracker_issue = TrackerIssue(
                    str(work_item_id),
                    created_ts,
                    resolution_ts,
                    self.get_app_name(work_item),
                )
                production_work_items.append(tracker_issue)
        if not production_work_items:
            # TODO should be warning?
            logging.debug("No issues were found")
        return production_work_items

#!/usr/bin/env python3
#
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
from typing import Iterable, Optional

from attrs import define, field, frozen

from committime import CommitMetric
from exporters.pelorus.deserialization import nested
from exporters.pelorus.utils.openshift_utils import CommonResourceInstance
from pelorus.timeutil import parse_guessing_timezone_DYNAMIC, to_epoch_from_string
from pelorus.utils import collect_bad_attribute_path_error, get_nested

from .collector_base import AbstractCommitCollector

COMMIT_TIME_DOCKER_LABEL = "io.openshift.build.commit.date"


@frozen
class DockerLabelInfo:
    namespace: Optional[str] = field(
        default=None, metadata=nested(["io.openshift.build.namespace"])
    )
    commit_time: Optional[str] = field(
        default=None, metadata=nested([COMMIT_TIME_DOCKER_LABEL])
    )
    commit_hash: Optional[str] = field(
        default=None, metadata=nested(["io.openshift.build.commit.id"])
    )


@frozen
class Image(CommonResourceInstance):
    "Relevant data from an `image.openshift.io/v1/Image`"

    # TODO: this doesn't seem right but was copied from previous code
    image_location: str = field(metadata=nested("dockerImageReference"))

    docker_labels: Optional[DockerLabelInfo] = field(
        default=None, metadata=nested("dockerImageMetadata.Config.Labels")
    )

    @property
    def hash(self):
        return self.metadata.name


@define(kw_only=True)
class ImageCommitCollector(AbstractCommitCollector):
    date_format: str

    date_annotation_name: str = CommitMetric._ANNOTATION_MAPPIG["commit_time"]

    # maps attributes to their location in a `image.openshift.io/v1`.
    # Similar to Build Mapping from committime.__init__.py
    _IMAGE_MAPPING = dict(
        image_hash=("metadata.name", True),
        image_location=("dockerImageReference", True),
        annotations=("metadata.annotations", False),
    )

    _DOCKER_LABEL_MAPPING = dict(
        namespace="io.openshift.build.namespace",
        commit_time="io.openshift.build.commit.date",
        commit_hash="io.openshift.build.commit.id",
        repo_url="io.openshift.build.source-location",
        committer="io.openshift.build.commit.author",
    )

    def commit_metric_from_image(self, app: str, image, errors: list) -> CommitMetric:
        """
        Create a CommitMetric from image.openshift.io/v1 information or Image annotation

        Some of the information such as image sha is gathered from the Image metadata,
        which we expect to always exists.

        For the commit time Image type exporter only commit time is required, however
        additional data is also collected such as commit hash.

        commit time which is converted to the commit timestamp is gathered from the
        Image Label, which normally is populated from the Docker build process as
        described in https://docs.openshift.com/online/pro/dev_guide/builds/build_output.html#output-image-labels

        If such information is missing from the Image Label there is a way to collect
        this data using annotations in similar way build annotations works.

        """
        metric = CommitMetric(app)
        image_labels = None

        # If exists get all Labels that were produced from Docker build process
        with collect_bad_attribute_path_error(errors, False):
            image_labels = get_nested(
                image, "dockerImageMetadata.Config.Labels", name="image"
            )

        # Get general data from image
        for attr_name, (path, required) in ImageCommitCollector._IMAGE_MAPPING.items():
            with collect_bad_attribute_path_error(errors, required):
                value = get_nested(image, path, name="image")
                setattr(metric, attr_name, value)

        # First get metrics within Labels
        attribute_mapping = (
            ImageCommitCollector._DOCKER_LABEL_MAPPING.items() if image_labels else []
        )
        for attr_name, label in attribute_mapping:
            value = image_labels.get(label)
            if value:
                if attr_name == "commit_time":
                    logging.debug(
                        "Commit time for image %s provided by '%s' label: %s",
                        metric.image_hash,
                        label,
                        value,
                    )
                setattr(metric, attr_name, value)

        if not metric.commit_time:
            metric = self._set_commit_time_from_annotations(metric, errors)

        if not metric.commit_hash:
            # We ignore all the errors by passing [], because commit hash isn't required.
            metric = self._set_commit_hash_from_annotations(metric, [])
        if not metric.commit_hash:
            # We ensure None is passed as string
            metric.commit_hash = "None"
        metric = self._set_commit_timestamp(metric, errors)

        if not metric.namespace:
            metric.namespace = "None"

        return metric

    def _set_commit_timestamp(self, metric: CommitMetric, errors) -> CommitMetric:
        # Only convert when commit_time is in metric, previously should be
        # found from the Label with fallback to annotation
        if metric.commit_time:
            try:
                metric.commit_timestamp = to_epoch_from_string(
                    metric.commit_time
                ).timestamp()
            except (ValueError, AttributeError):
                # Do nothing here as we tried with EPOCH timestamp
                metric.commit_timestamp = parse_guessing_timezone_DYNAMIC(
                    metric.commit_time, format=self.date_format
                ).timestamp()
        return metric

    def get_commit_time(self, metric) -> Optional[CommitMetric]:
        return super().get_commit_time(metric)

    def _set_commit_time_from_annotations(
        self, metric: CommitMetric, errors: list
    ) -> CommitMetric:
        if not metric.commit_time:
            commit_time = metric.annotations.get(self.date_annotation_name)
            if commit_time:
                metric.commit_time = commit_time.strip()
                logging.debug(
                    "Commit time for image %s provided by '%s'",
                    metric.image_hash,
                    metric.commit_time,
                )
            else:
                errors.append(
                    "Couldn't get commit time from annotations nor image label"
                )
        return metric

    # overrides collector_base.generate_metric()
    def generate_metrics(self) -> Iterable[CommitMetric]:
        # Initialize metrics list
        metrics = []
        app_label = self.app_label

        logging.debug("Searching for images with label: %s" % app_label)

        v1_images = self.kube_client.resources.get(
            api_version="image.openshift.io/v1", kind="Image"
        )

        images = v1_images.get(label_selector=app_label)

        images_by_app = self._get_openshift_obj_by_app(images)

        if images_by_app:
            metrics += self._get_metrics_by_apps_from_images(images_by_app)

        return metrics

    def _get_metrics_by_apps_from_images(self, images_by_app):
        metrics = []
        for app in images_by_app:
            images = images_by_app[app]
            for image in images:
                metric = None
                errors = []

                try:
                    metric = self.commit_metric_from_image(app, image, errors)
                except Exception:
                    logging.error(
                        "Cannot collect metrics from image: %s" % (image.metadata.name)
                    )
                    raise

                if errors:
                    msg = (
                        f"Missing data for CommitTime metric from Image "
                        f"{metric.image_hash} in app {app}: "
                        f"{'.'.join(str(e) for e in errors)}"
                    )
                    logging.warning(msg)
                    continue

                logging.debug("Adding metric for app %s" % app)
                metrics.append(metric)

        return metrics

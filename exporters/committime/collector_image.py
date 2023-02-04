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
from pelorus.deserialization import DeserializationErrors, deserialize, nested
from pelorus.deserialization.errors import MissingFieldWithMultipleSourcesError
from pelorus.timeutil import parse_guessing_timezone_DYNAMIC, to_epoch_from_string
from pelorus.utils.openshift_utils import CommonResourceInstance

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

    date_annotation_name: str = CommitMetric._ANNOTATION_MAPPING["commit_time"]

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

    def commit_metric_from_image(self, app: str, image: Image) -> CommitMetric:
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

        missing: list[MissingFieldWithMultipleSourcesError] = []

        # TODO: there's a lot here that is pseudo-required.
        # instead of assigning "None", we should consider raising a DeserializationErrors exception.
        docker_labels = image.docker_labels

        commit_time_str = docker_labels and docker_labels.commit_time

        if commit_time_str:
            logging.debug(
                "Commit time for image %s provided by '%s' label: %s",
                image.hash,
                COMMIT_TIME_DOCKER_LABEL,
                commit_time_str,
            )

        if not commit_time_str:
            commit_time_str = self._get_commit_time_from_annotations(image)
        else:
            # TODO: make the source names more descriptive / accurate
            missing.append(
                MissingFieldWithMultipleSourcesError(
                    "commit_time", [COMMIT_TIME_DOCKER_LABEL, self.date_annotation_name]
                )
            )

        commit_hash = docker_labels and docker_labels.commit_hash

        if not (commit_hash):
            commit_hash = self._get_commit_hash_from_annotations(
                input.metadata.annotations
            )
        if not commit_hash:
            # TODO: is this valid? Should we just skip the metric and log an error?
            # would add to missing list here.
            commit_hash = "None"

        if not commit_time_str:
            raise DeserializationErrors(missing)

        try:
            commit_time = to_epoch_from_string(commit_time_str)
        except (ValueError, AttributeError):
            commit_time = parse_guessing_timezone_DYNAMIC(
                commit_time_str, format=self.date_format
            )

        # TODO: when would this happen? should we even allow it? does it matter?
        # would add to missing list here.
        namespace = docker_labels and docker_labels.namespace or "None"

        return CommitMetric(
            app,
            namespace=namespace,
            image_hash=image.hash,
            commit_timestamp=commit_time,
            commit_hash=commit_hash,
        )

    def _get_commit_time_from_annotations(self, image: Image):
        return image.metadata.annotations.get(self.date_annotation_name)

    def generate_metrics(self) -> Iterable[CommitMetric]:
        "Generate metrics from all known images."

        metrics: list[CommitMetric] = []
        app_label = self.app_label

        logging.debug("Searching for images with label: %s", app_label)

        v1_images = self.kube_client.resources.get(
            api_version="image.openshift.io/v1", kind="Image"
        )

        images = v1_images.get(label_selector=app_label)

        images = [
            deserialize(
                image,
                Image,
                src_name="OpenShift dynamic Image",
                target_name="image info",
            )
            for image in images.items
        ]

        images_by_app = self._get_openshift_obj_by_app(images)

        if images_by_app:
            metrics += self._get_metrics_by_apps_from_images(images_by_app)

        return metrics

    def _get_metrics_by_apps_from_images(
        self, images_by_app: dict[str, list[Image]]
    ) -> list[CommitMetric]:
        metrics: list[CommitMetric] = []
        for app, images in images_by_app.items():
            for image in images:

                try:
                    metric = self.commit_metric_from_image(app, image)
                    logging.debug("Adding metric for app %s", app)
                    metrics.append(metric)
                except MissingFieldWithMultipleSourcesError as e:
                    logging.warning(
                        "Image %s/%s is missing necessary data: %s",
                        image.metadata.namespace,
                        image.metadata.name,
                        e,
                    )
                except Exception:
                    logging.error(
                        "Cannot collect metrics from image: %s", exc_info=True
                    )
                    raise

        return metrics

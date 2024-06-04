"""
Type stubs to make working with openshift objects a little easier.
These are not meant to be "real" types. Instead, you can claim
that untyped, dynamic data from openshift "fits" these shapes.

These should probably be type stubs only, but I can't figure
out how to do that yet.
"""
from typing import TypeVar

import attrs


@attrs.frozen
class Metadata:
    """
    OpenShift metadata. Almost always guaranteed to be present.
    """

    name: str
    namespace: str
    labels: dict[str, str]
    annotations: dict[str, str]


@attrs.frozen
class CommonResourceInstance:
    "Resource instances that we work with usually have the typical metadata."
    apiVersion: str
    kind: str
    metadata: Metadata


R = TypeVar("R", bound=CommonResourceInstance)

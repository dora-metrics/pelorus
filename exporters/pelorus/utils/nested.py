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
"""
Utilities for working with nested data.

Working with openshift objects means looking at deeply nested data.
Having an easy way to access this data through a "path" is useful.

These tools enable:
- rich errors detailing where in a path data was missing
- easily accessing nested data with barely more boilerplate than naive python
- easily accessing key names that contain dots

A path is canonically represented as a sequence/list of keys to use as
getitem lookups (`item[key]`). They can be input as a "string.with.dots"
for convenience. The sequence/list form is required when a key contains
dots itself, such as when accessing openshift labels or annotations.
"""
import contextlib
import enum
from typing import Any, Literal, Mapping, Optional, Sequence, TypeVar, Union, overload

import attrs

T = TypeVar("T")
U = TypeVar("U")


# sentinel value for the default kwarg to get_nested
class _NoDefault(enum.Enum):
    NO_DEFAULT = enum.auto()


@overload
def get_nested(
    root: Mapping[str, T],
    path: Union[Sequence[str], str],
    *,
    name: Optional[str] = None,
) -> T:
    ...


@overload
def get_nested(
    root: Mapping[str, T],
    path: Union[Sequence[str], str],
    *,
    default: U,
    name: Optional[str] = None,
) -> Union[T, U]:
    ...


def get_nested(
    root: Mapping[str, T],
    path: Union[Sequence[str], str],
    *,
    default: Union[U, Literal[_NoDefault.NO_DEFAULT]] = _NoDefault.NO_DEFAULT,
    name: Optional[str] = None,
) -> Union[T, U]:
    """
    `get_nested` helps you safely traverse a deeply nested object that is indexable.
    If `TypeError`, `KeyError`, or `IndexError` are thrown, then `default` will be returned.
    If `default` is not given, a `MissingAttributeError` will be thrown,
    which includes information about where in the path things went wrong, and a human-readable name (if included).

    You may specify the path as either a list of keys, or a single string.
    The string will be split on '.' so you can emulate the nested attribute lookup `ResourceField`
    would offer.

    A `name` for the item, if specified, makes the error message in the exception more useful.

    Kubernetes API items often are deeply nested, with any number of fields that could be absent.
    When using an `openshift.dynamic.ResourceField`, it will turn attribute accesses into
    dictionary accesses. Normally, a deeply nested access like item.status.ref.foo.bar has four different spots
    you could get an `AttributeError`. With a `ResourceField`, there are actually only three, since `item.status`
    will return `None` if `status` is absent, but `None` will not have a `ref` field, leading to an
    AttributeError.
    """
    item = root
    path = split_path(path)

    for i, key in enumerate(path):
        try:
            item = item[key]  # type: ignore
        except (TypeError, IndexError, KeyError) as e:
            if default is not _NoDefault.NO_DEFAULT:
                return default

            raise BadAttributePathError(
                path=path,
                path_slice=slice(i),
                key=key,
                value=item,
                root_name=name,
            ) from e

    return item


def split_path(path: Union[str, Sequence[str]]) -> Sequence[str]:
    """
    Idempotently split a path for use in nested access.

    >>> assert split_path("foo.bar") == ("foo", "bar")
    >>> assert split_path(["foo", "has.dots", "bar"]) == ["foo", "has.dots", "bar"]
    """
    if isinstance(path, str):
        # `if part` filters out leading dot (or accidental double dots, technically)
        return tuple(part for part in path.split(".") if part)
    else:
        return path


def format_path(path: Sequence[str]) -> str:
    """
    Format a path for readability.

    >>> assert format_path("foo.bar".split(".")) == "foo.bar"
    >>> assert format_path(["foo", "has.dots", "bar"]) == "foo[has.dots].bar"
    """
    formatted = ""
    for part in path:
        if "." in part:
            formatted += f"[{part}]"
        else:
            formatted += f".{part}"
    return formatted if formatted[0] != "." else formatted[1:]


@attrs.frozen
class BadAttributePathError(Exception):
    """
    An error representing a nested lookup that went wrong.

    root is the root item the attribute accesses started from.
    path is the whole path that was meant to be accessed.
    path_slice represents how far in the path we got before an issue was encountered.
    value is the value that the last good attribute access returned.
    root_name is the name of the root item, which makes the error message more helpful.
    """

    path: Sequence[str]
    path_slice: slice
    key: str
    value: Any
    root_name: Optional[str] = None

    @property
    def message(self) -> str:
        msg = f"{self.root_name + ' is missing' if self.root_name else 'Missing'} {self.key}"

        # keep message simple if there's only one child we tried to access,
        # but otherwise add detail
        if len(self.path) > 1:
            msg += (
                f" in {format_path(self.path)} because "
                f"{'.'.join(self.path[self.path_slice])} was {self.value}"
            )

        return msg

    def __str__(self):
        return self.message


@contextlib.contextmanager
def collect_bad_attribute_path_error(error_list: list, append: bool = True):
    """
    If a BadAttributePathError is raised, append it to the list of errors and continue.
    If append is set to False then error will not be appended to the list of errors.
    """
    try:
        yield
    except BadAttributePathError as e:
        if append:
            error_list.append(e)


__all__ = ["get_nested", "BadAttributePathError", "collect_bad_attribute_path_error"]

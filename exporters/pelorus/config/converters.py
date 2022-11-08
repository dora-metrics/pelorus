"""
Converters to augment `attrs.converters`,
and tools to integrate them with our config system.
"""
import re
from typing import Callable, Collection, Iterator, TypeVar, Union

CollectionType = TypeVar("CollectionType", bound=Collection[str])

T = TypeVar("T")
U = TypeVar("U")


def comma_separated(
    collection: Callable[[Iterator[str]], CollectionType]
) -> Callable[[Union[str, CollectionType]], CollectionType]:
    """
    Returns a converter for the collection that will
    split a comma-separated string, stripping whitespace from each element.

    If a string is not given, it is assumed to be the target
    collection type and is returned as-is. (Useful for testing.)
    """

    def _converter(value: Union[str, CollectionType]):
        if isinstance(value, str):
            return collection(part.strip() for part in value.split(","))
        else:
            return value

    return _converter


def comma_or_whitespace_separated(
    collection: Callable[[Iterator[str]], CollectionType]
) -> Callable[[Union[str, CollectionType]], CollectionType]:
    """
    Returns a converter for the collection that will
    split a string on whitespace or commas.

    If a string is not given, it is assumed to be the target
    collection type and is returned as-is. (Useful for testing.)
    """

    def _converter(value: Union[str, CollectionType]):
        if isinstance(value, str):
            replaced = re.sub(r"\s+", ",", value)
            return collection(part.strip() for part in replaced.split(","))
        else:
            return value

    return _converter


def pass_through(
    type: type[U], converter: Callable[[T], U]
) -> Callable[[Union[T, U]], U]:
    "Pass through the input if it is the given type, otherwise use the converter."

    def _pass_through(value: Union[T, U]) -> U:
        if isinstance(value, type):
            return value
        else:
            return converter(value)  # type: ignore

    return _pass_through


__all__ = ["comma_separated", "comma_or_whitespace_separated", "pass_through"]

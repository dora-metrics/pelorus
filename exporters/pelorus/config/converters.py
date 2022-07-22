"""
Converters to augment `attrs.converters`,
and tools to integrate them with our config system.
"""
from functools import partial
from typing import Callable, Collection, Iterator, TypeVar, Union

CollectionType = TypeVar("CollectionType", bound=Collection[str])


def comma_separated(
    collection: Callable[[Iterator[str]], CollectionType]
) -> Callable[[Union[str, CollectionType]], CollectionType]:
    """
    Returns a converter for the collection that will
    split a comma-separated string, stripping whitespace from each element.

    If a string is not given, it is assumed to be the target
    collection type and is returned as-is. (Useful for testing.)
    """
    return partial(_comma_separated_collection, collection)


def _comma_separated_collection(
    collection: Callable[[Iterator[str]], CollectionType],
    val: Union[str, CollectionType],
) -> CollectionType:
    if isinstance(val, str):
        return collection(part.strip() for part in val.split(","))
    else:
        return val


__all__ = ["comma_separated"]

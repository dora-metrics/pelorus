"""
Module utils contains helper utilities for common tasks in the codebase.
They are mainly to help with type information and to deal with data structures
in kubernetes that are not so idiomatic to deal with.
"""
import dataclasses
from collections import UserString
from collections.abc import Iterable
from typing import Any, Optional, Protocol, TypeVar, Union, overload

__FIRST_NO_DEFAULT = object()
T = TypeVar("T")
U = TypeVar("U")


@overload
def first(iterable: Iterable[T]) -> T:
    ...


@overload
def first(iterable: Iterable[T], *, default: U) -> Union[T, U]:
    ...


def first(iterable: Iterable[T], *, default: U = __FIRST_NO_DEFAULT) -> Union[T, U]:
    """
    First wraps next() to make its use as "return the first member of this iterable"
    more clear, and to make default a keyword only argument.
    """
    if default is __FIRST_NO_DEFAULT:
        return next(iter(iterable))
    else:
        return next(iter(iterable), default)


K = TypeVar("K")
V = TypeVar("V")


class NameValueNamespace(Protocol[K, V]):
    """
    A representation of an object that has name and value fields.
    """

    name: K
    value: V


def name_value_attrs_to_dict(
    name_values: Iterable[NameValueNamespace[K, V]]
) -> dict[K, V]:
    """
    Kubernetes commonly expresses mappings as a list of objects with two entries: `name` and `value`.
    This converts those to a dict.
    """
    return {x.name: x.value for x in name_values}


__GET_NESTED_NO_DEFAULT = object()


@overload
def get_nested(
    root: Any,
    path: Union[list[Any], str],
    *,
    name: str = None,
) -> Any:
    ...


@overload
def get_nested(
    root: Any,
    path: Union[list[Any], str],
    *,
    default: Any,
    name: str = None,
) -> Any:
    ...


def get_nested(
    root: Any,
    path: Union[list[Any], str],
    default: Any = __GET_NESTED_NO_DEFAULT,
    name: str = None,
) -> Any:
    """
    `get_nested` helps you safely traverse a deeply nested object that is indexable.
    If `TypeError`, `KeyError`, or `IndexError` are thrown, then `default` will be returned.
    If `default` is not given, a `MissingAttributeError` will be thrown,
    which includes information about where in the path things went wrong, and a human-readable name (if included).

    You may specify the path as either an iterable of keys / indexes, or a single string.
    The string will be split on '.' so you can emulate the nested attribute lookup `ResourceField`
    would offer.

    A `name` for the item, if specified, makes the error message in the exception more useful.

    Kubernetes API items often are deeply nested, with any number of fields that could be absent.
    When using an `openshift.dynamic.ResourceField`, it will turn attribute accesses into
    dictionary accesses. Normally, a deeply nested access like item.status.ref.foo.bar has four different spots
    you could get an `AttributeError`. With a `ResourceField`, there are actually only three, since `item.status`
    will return `None` if `status` is absent, but `None` will not have a `ref` field, leading to an
    AttributeError.

    This all may be unnecessary once Python 3.11 comes out, because of PEP-0647:
    https://www.python.org/dev/peps/pep-0657/
    """
    item = root
    if isinstance(path, str):
        # filter out leading dot (or accidental double dots, technically)
        path = [part for part in path.split(".") if part]
    for i, key in enumerate(path):
        try:
            item = item[key]
        except (TypeError, IndexError, KeyError):
            if default is not __GET_NESTED_NO_DEFAULT:
                return default

            raise BadAttributePathError(
                root=root,
                path=path,
                path_slice=slice(i),
                value=item,
                root_name=name,
            )

    return item


@dataclasses.dataclass
class BadAttributePathError(Exception):
    """
    An error representing a nested lookup that went wrong.
    """

    root: Any
    path: list[Any]
    path_slice: slice
    value: Any
    root_name: Optional[str] = None

    @property
    def message(self):
        return (
            f"While trying to look up {'.'.join(self.path)} within "
            f"{self.root_name if self.root_name else 'an item'}, "
            f"{'.'.join(self.path[self.path_slice])} was {self.value}, "
            "so we could not continue."
        )


class TypedString(UserString):
    """
    A "wrapped" string that can only test for equality between TypedStrings
    of the same type, or a regular string.

    This helps when strings representing different things are easily confused--
    such as PipelineRun names versus Pipeline names.
    """

    def __eq__(self, other):
        if isinstance(other, TypedString):
            if type(self) is type(other):
                return self.data == other.data
            else:
                return False
        elif type(other) is str:
            return self.data == other
        else:
            return NotImplemented

    def __repr__(self):
        type_name = type(self).__name__
        return f'{type_name}("{super().__str__()}")'

    def __hash__(self) -> int:
        return super().__hash__()

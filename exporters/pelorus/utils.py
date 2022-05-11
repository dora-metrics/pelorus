"""
Module utils contains helper utilities for common tasks in the codebase.
They are mainly to help with type information and to deal with data structures
in kubernetes that are not so idiomatic to deal with.
"""
import contextlib
import dataclasses
import logging
import os
from typing import Any, Optional, Union, overload

# sentinel value for the default kwarg to get_nested
__GET_NESTED_NO_DEFAULT = object()

DEFAULT_VAR_KEYWORD = "default"


@overload
def get_nested(
    root: Any,
    path: Union[list[Any], str],
    *,
    name: Optional[str] = None,
) -> Any:
    ...


@overload
def get_nested(
    root: Any,
    path: Union[list[Any], str],
    *,
    default: Any,
    name: Optional[str] = None,
) -> Any:
    ...


def get_nested(
    root: Any,
    path: Union[list[Any], str],
    *,
    default: Any = __GET_NESTED_NO_DEFAULT,
    name: Optional[str] = None,
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
        except (TypeError, IndexError, KeyError) as e:
            if default is not __GET_NESTED_NO_DEFAULT:
                return default

            raise BadAttributePathError(
                root=root,
                path=path,
                path_slice=slice(i),
                value=item,
                root_name=name,
            ) from e

    return item


@dataclasses.dataclass
class BadAttributePathError(Exception):
    """
    An error representing a nested lookup that went wrong.

    root is the root item the attribute accesses started from.
    path is the whole path that was meant to be accessed.
    path_slice represents how far in the path we got before an issue was encountered.
    value is the value that the last good attribute access returned.
    root_name is the name of the root item, which makes the error message more helpful.
    """

    root: Any
    path: list[Any]
    path_slice: slice
    value: Any
    root_name: Optional[str] = None

    @property
    def message(self):
        return (
            f"{self.root_name + ' is missing' if self.root_name else 'Missing'}"
            f" {'.'.join(self.path)} because "
            f"{'.'.join(self.path[self.path_slice])} was {self.value}"
        )

    def __str__(self):
        return self.message


@contextlib.contextmanager
def collect_bad_attribute_path_error(error_list: list):
    """
    If a BadAttributePathError is raised, append it to the list and continue.
    """
    try:
        yield
    except BadAttributePathError as e:
        error_list.append(e)


class SpecializeDebugFormatter(logging.Formatter):
    """
    Uses a different format for DEBUG messages that has more information.
    """

    DEBUG_FORMAT = "%(asctime)-15s %(levelname)-8s %(pathname)s:%(lineno)d %(funcName)s() %(message)s"

    def format(self, record):
        prior_format = self._style._fmt

        try:
            if record.levelno == logging.DEBUG:
                self._style._fmt = self.DEBUG_FORMAT

            return logging.Formatter.format(self, record)
        finally:
            self._style._fmt = prior_format


def get_env_var(var_name: str, default_value: Optional[str] = None) -> Optional[str]:
    """
    `get_env_var` modifies standard os.getenv behavior to allow using default python variable values
    when:
        1. PELORUS_DEFAULT_KEYWORD is set in SHELL env and the value from PELORUS_DEFAULT_KEYWORD
           is used for other SHELL env value, e.g.
           export PELORUS_DEFAULT_KEYWORD="custom_default"
           export LOG_LEVEL="custom_default"

           In which case LOG_LEVEL is set to DEFAULT_LOG_LEVEL

        2. DEFAULT_VAR_KEYWORD keyword is present as the SHELL env variable value, e.g.
           unset PELORUS_DEFAULT_KEYWORD
           export LOG_LEVEL="default"

           In which case LOG_LEVEL is set to DEFAULT_LOG_LEVEL

    This is required for the config map to define fallback vars in a consistent way.
    """
    default_keyword = os.getenv("PELORUS_DEFAULT_KEYWORD") or DEFAULT_VAR_KEYWORD

    env_var = os.getenv(var_name, default_value)
    if env_var == default_keyword:
        if default_value is None:
            raise ValueError(f"default value not present for SHELL env var: {var_name}")
        return default_value

    return env_var

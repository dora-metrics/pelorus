"""
A declarative way to load configuration from environment variables, and log that configuration properly.

See the [README](./README.md) file for documentation.
See [DEVELOPING](./DEVELOPING.md) for implementation details / dev docs.
"""

import logging
import os
from typing import Any, Generic, Mapping, Optional, Type, TypeVar

import attrs

from pelorus.config.loading import (
    MissingConfigDataError,
    MissingDataError,
    ValueWithSource,
    _EnvFinder,
    env_vars,
    no_env_vars,
)
from pelorus.config.log import LOG, REDACT, SKIP, Log, log
from pelorus.utils import DEFAULT_VAR_KEYWORD


def _prepare_kwargs(results: dict[str, Any]):
    """
    Handle the following cases:

    Attrs removes underscores from field names for the init param names,
    so we need to change the field names for the kwargs.

    We wrap values in classes describing where they came from, so we need to unpack those.
    """
    for k, v in results.items():
        if isinstance(v, ValueWithSource):
            value = v.value
        else:
            value = v

        yield k.lstrip("_"), value


ConfigClass = TypeVar("ConfigClass")


@attrs.frozen
class _LoggingLoader(Generic[ConfigClass]):
    """
    Load values for the given class from the environment (overridden by `other`),
    logging their values and reporting errors, before instantiating the class.
    """

    cls: Type[ConfigClass]
    other: dict[str, Any]
    env: Mapping[str, str]
    default_keyword: str
    logger: logging.Logger

    results: dict[str, Any] = attrs.field(factory=dict, init=False)
    errors: list[MissingDataError] = attrs.field(factory=list, init=False)

    def _load(self):
        for field in attrs.fields(self.cls):
            if not field.init:
                # field does not get set during instance creation,
                # so don't load it.
                continue

            name = field.name

            value = _EnvFinder.get_value(
                field, self.env, self.other, self.default_keyword
            )

            if isinstance(value, MissingDataError):
                self.results[name] = value
                self.errors.append(value)
            else:
                self.results[name] = value

    def _log(self):
        if self.errors:
            log_with_level = self.logger.error
            log_with_level(
                "While loading config %s, errors were encountered. All values:",
                self.cls.__name__,
            )
        else:
            log_with_level = self.logger.info
            log_with_level("Loading %s, inputs below:", self.cls.__name__)

        for field, value in self.results.items():
            if isinstance(value, ValueWithSource):
                if value.log is SKIP:
                    continue

                source = value.source()

                if value.log is REDACT:
                    value = "REDACTED"
                else:
                    value = repr(value.value)

                log_with_level("%s=%s, %s", field, value, source)
            elif isinstance(value, MissingDataError):
                log_with_level("%s=ERROR: %s", field, value)

    def load_and_log(self) -> ConfigClass:
        self._load()
        self._log()

        if self.errors:
            raise MissingConfigDataError(self.cls.__name__, self.errors)

        kwargs = dict(_prepare_kwargs(self.results))

        return self.cls(**kwargs)


def load_and_log(
    cls: Type[ConfigClass],
    other: dict[str, Any] = {},
    *,
    env: Mapping[str, str] = os.environ,
    default_keyword: Optional[str] = None,
    logger: logging.Logger = logging.getLogger(__name__),
) -> ConfigClass:
    """
    Load values for the given class from the environment,
    logging their values and reporting errors, before instantiating the class.

    `other` is used for variables that can't be loaded from the environment,
    or to override the environment and skip checking it for their values.
    The names in `other` are the _field name_, not the env var name.

    env defaults to os.environ, and can be overridden for testing.

    default_keyword may be overridden. If the default of `None`,
    the env var of `PELORUS_DEFAULT_KEYWORD` is used, falling back to "default".
    This is looked up from `env`, not necessarily os.environ.

    logger defaults to the logger for `pelorus.config`, but may be overridden.
    """
    if default_keyword is None:
        default = env.get("PELORUS_DEFAULT_KEYWORD", DEFAULT_VAR_KEYWORD)
    else:
        default = default_keyword

    loader = _LoggingLoader(
        cls, other=other, env=env, default_keyword=default, logger=logger
    )
    return loader.load_and_log()


__all__ = [
    "load_and_log",
    "log",
    "LOG",
    "Log",
    "SKIP",
    "REDACT",
    "env_vars",
    "no_env_vars",
]

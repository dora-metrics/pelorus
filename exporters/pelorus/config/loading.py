from typing import Any, Collection, Literal, Mapping, Optional, Sequence, Union

import attrs
from attrs import Attribute, frozen

from pelorus.config.common import Metadata
from pelorus.config.log import SKIP, Log, _get_log_meta, _should_log
from pelorus.utils._attrs_compat import NOTHING, Factory

_ENV_LOOKUPS_KEY = "__pelorus_config_env_vars"


def env_vars(*lookups: str) -> Metadata:
    """
    Each environment variable listed will be queried until a value is found.
    """
    return {_ENV_LOOKUPS_KEY: lookups}


def no_env_vars() -> Metadata:
    """
    This field should not be loaded from the environment.
    It will have to be passed through `other`.
    """
    return {_ENV_LOOKUPS_KEY: tuple()}


# region: errors
class MissingDataError(Exception):
    """
    Parent error for any data missing during loading.
    """

    pass


@frozen
class MissingVariable(MissingDataError):
    """
    A required variable was missing.
    """

    name: str
    env_lookups: Sequence[str]

    def __str__(self):
        if len(self.env_lookups) == 1:
            env_lookup_str = f"env var {self.env_lookups[0]}"
        else:
            env_lookup_str = "any of " + ",".join(self.env_lookups)

        return f"{self.name} was not found in {env_lookup_str}"


@frozen
class MissingDefault(MissingDataError):
    """
    A variable was set to "default" but there was no default set.
    """

    name: str
    var_containing_default: str
    default_keyword: str

    def __str__(self):
        return (
            f"{self.name} was set to {self.default_keyword} "
            f"in env var {self.var_containing_default} but there was no default set"
        )


@frozen
class MissingOther(MissingDataError):
    """
    A variable had environment lookups disabled, but was not passed in `other`.
    """

    name: str

    def __str__(self):
        return f"{self.name} had environment lookups disabled, but was not passed in to `load`'s `other` dict."


class MissingConfigDataError(Exception):
    """
    Collects all missing env var issues into one error.
    """

    def __init__(self, config_class: str, missing: Collection[MissingDataError]):
        super().__init__()
        self.config_class = config_class
        self.missing = missing

    def __str__(self):
        return f"Config for {self.config_class} is missing data: " + "\n".join(
            str(x) for x in self.missing
        )


# endregion

# region: successes


@frozen
class ValueWithSource:
    """
    The result of a variable / value lookup, with information about how the value was obtained.
    Also notes the field's log status.
    """

    value: Any
    log: Log = attrs.field(kw_only=True)

    def source(self) -> str:
        ...


@frozen
class FoundEnvVar(ValueWithSource):
    "Found it in an env var"
    env_name: str

    def source(self):
        return f"from env var {self.env_name}"


@frozen
class UnsetEnvVar(ValueWithSource):
    "No env var, came from attrs"
    env_lookups: tuple[str]

    def source(self):
        if len(self.env_lookups) == 1:
            return f"default value; {self.env_lookups[0]} was not set"
        else:
            return "default value; none of " + ", ".join(self.env_lookups) + " were set"


@frozen
class DefaultSetEnvVar(ValueWithSource):
    "Env var was set to default keyword"
    env_name: str
    default_keyword: str

    def source(self):
        return f"default value ({self.env_name} set to {self.default_keyword})"


@frozen
class OtherVar(ValueWithSource):
    "Value came from `other` dict"

    def source(self):
        return "passed in from `other` dict"


# endregion


@frozen
class _EnvFinder:
    "Load from environment or get default"
    field: Attribute
    env: Mapping[str, str]
    env_lookups: tuple[str]
    default_keyword: str
    other: Mapping[str, Any]

    @property
    def name(self):
        """
        Field name.
        """
        return self.field.name

    def _first_env_match(self) -> Optional[str]:
        """
        Return the _name_ of the first present env var.
        Returns `None` if none were present.
        """
        for name in self.env_lookups:
            if name in self.env:
                return name
        return None

    def _get_default(self) -> Union[Any, Literal[NOTHING]]:
        """
        Get the default value for this field, invoking the attrs.Factory if necessary.
        Returns `NOTHING` if there was no default defined.

        """
        default = self.field.default
        if isinstance(default, Factory):
            if default.takes_self:
                raise ValueError(
                    "Factories used for config loading cannot use takes_self"
                )
            return default.factory()
        else:
            return default

    def _value_or_default(self) -> Union[ValueWithSource, MissingDataError]:
        """
        Get the value wrapped with information about where it came from,
        or return the descriptive error for its absence.
        """
        if self.name in self.other:
            return OtherVar(
                self.other[self.name], log=_get_log_meta(self.field.metadata) or SKIP
            )
        elif not self.env_lookups:
            # should have been in other but was not.
            return MissingOther(self.name)

        env_name = self._first_env_match()

        if env_name is None:
            value = self._get_default()
            if value is NOTHING:
                return MissingVariable(self.name, self.env_lookups)
            else:
                return UnsetEnvVar(
                    value, env_lookups=self.env_lookups, log=_should_log(self.field)
                )

        value = self.env[env_name]
        if value == self.default_keyword:
            value = self._get_default()
            if value is NOTHING:
                return MissingDefault(self.name, env_name, self.default_keyword)
            else:
                return DefaultSetEnvVar(
                    env_name=env_name,
                    value=value,
                    default_keyword=self.default_keyword,
                    log=_should_log(self.field),
                )

        return FoundEnvVar(env_name=env_name, value=value, log=_should_log(self.field))

    @classmethod
    def get_value(
        cls,
        field: Attribute,
        env: Mapping[str, str],
        other: Mapping[str, Any],
        default_keyword: str,
    ) -> Union[ValueWithSource, MissingDataError]:
        """
        Loads the value from the environment, handling various default-fallback scenarios.
        """
        if _ENV_LOOKUPS_KEY in field.metadata:
            env_lookups = field.metadata[_ENV_LOOKUPS_KEY]
        else:
            env_lookups = (field.name.upper(),)

        return cls(field, env, env_lookups, default_keyword, other)._value_or_default()

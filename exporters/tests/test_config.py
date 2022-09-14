from typing import Optional

import pytest
from attrs import define, field

import pelorus
from pelorus.config import load_and_log
from pelorus.config.converters import comma_separated
from pelorus.config.loading import env_vars, no_env_vars
from pelorus.config.log import LOG, Log, log


def test_loading_simple_string():
    @define
    class SimpleCase:
        unannotated: str
        with_var: str = field()

    env = dict(UNANNOTATED="unannotated", WITH_VAR="with_var", FIELD_WORKS="field")

    loaded = load_and_log(SimpleCase, env=env)

    assert loaded.unannotated == env["UNANNOTATED"]
    assert loaded.with_var == env["WITH_VAR"]


def test_default():
    @define
    class Default:
        foo: str = field(default="foo")
        bar: str = "default from literal"
        baz: Optional[str] = None

    loaded = load_and_log(Default, env=dict())

    assert loaded.foo == "foo"
    assert loaded.bar == "default from literal"
    assert loaded.baz is None


def test_fallback_lookups():
    @define
    class Fallback:
        foo: str = field(metadata=env_vars("FOO", "BAR", "BAZ"))

    env = dict(BAR="bar", BAZ="baz")

    loaded = load_and_log(Fallback, env=env)

    assert loaded.foo == env["BAR"]


def test_load_collections():
    @define
    class Collections:
        a_set: set[str] = field(converter=comma_separated(set))
        a_tuple: tuple[str] = field(converter=comma_separated(tuple))
        a_list: list[str] = field(converter=comma_separated(list))
        default_list: list[str] = field(factory=list, converter=comma_separated(list))

    expected_list = ["one", "two", "three"]
    expected_tuple = ("one", "two", "three")
    expected_set = {"one", "two", "three"}

    env = dict(
        A_SET="one,two,three,one", A_LIST="one,two,three", A_TUPLE="one,two,three"
    )

    loaded = load_and_log(Collections, env=env)

    assert loaded.a_set == expected_set
    assert loaded.a_tuple == expected_tuple
    assert loaded.a_list == expected_list
    assert loaded.default_list == []


def test_loading_from_other():
    @define
    class OtherConfig:
        foo: object = field(metadata=no_env_vars())

    foo = object()

    loaded = load_and_log(OtherConfig, other=dict(foo=foo))

    assert loaded.foo is foo


def test_logging(caplog: pytest.LogCaptureFixture):
    pelorus.setup_logging()

    @define(kw_only=True)
    class Loggable:
        regular_field: str = field(default="LOG ME 1")

        sensitive_credential: str = field(default="REDACT ME 1")
        log_this_credential_anyway: str = field(
            default="LOG ME 2", metadata=log(Log.LOG)
        )
        explicitly_sensitive: str = field(
            default="REDACT ME 2", metadata=log(Log.REDACT)
        )

        _private_field: str = field(default="SHOULD BE ABSENT 1")
        _private_but_log_me_anyway: str = field(
            default="LOG ME 3", metadata=log(Log.LOG)
        )
        _private_but_redact_me: str = field(
            default="REDACT ME 3", metadata=log(Log.REDACT)
        )
        not_private_but_skip_logging: str = field(
            default="SHOULD BE ABSENT 2", metadata=log(Log.SKIP)
        )

        from_multi_env: str = field(
            default="", metadata=env_vars("MULTI_ENV", "FROM_MULTI_ENV")
        )
        default_name: str = field(default="LOG ME 4")

        other_not_logged: str = field(metadata=no_env_vars())
        other_explicitly_logged: str = field(metadata=no_env_vars() | log(LOG))

    load_and_log(
        Loggable,
        env=dict(DEFAULT_NAME="default"),
        other=dict(
            other_not_logged="SHOULD BE ABSENT 3", other_explicitly_logged="LOG ME 5"
        ),
    )

    logged = caplog.text

    assert "REDACT ME" not in logged
    assert "SHOULD BE ABSENT" not in logged
    for i in range(1, 6):
        assert f"LOG ME {i}" in logged

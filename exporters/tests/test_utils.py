import os

import pytest

import pelorus
from pelorus.utils import (
    BadAttributePathError,
    collect_bad_attribute_path_error,
    get_env_var,
    get_nested,
)

ROOT = dict(foo=dict(bar=dict()))
PATH = "foo.bar.baz.quux"
SLICED_PATH = ("foo", "bar")
VALUE = dict()


def test_nested_lookup_default():
    assert get_nested(ROOT, PATH, default=None) is None


def test_nested_lookup_exception():
    with pytest.raises(BadAttributePathError) as e:
        get_nested(ROOT, PATH)

    error = e.value
    assert error.path[error.path_slice] == SLICED_PATH
    assert error.value == VALUE


def test_nested_lookup_collect():
    errors = []

    with collect_bad_attribute_path_error(errors):
        get_nested(ROOT, PATH)

    assert len(errors) == 1
    error = errors[0]
    assert error.path[error.path_slice] == SLICED_PATH
    assert error.value == VALUE


@pytest.fixture(autouse=True)
def _clean_env_vars():
    """Ensure env vars are cleaned up before and after each test."""
    keys = ["PELORUS_DEFAULT_KEYWORD", "PELORUS_TEST_ENV_VAR_DEFAULT"]
    for key in keys:
        os.environ.pop(key, None)
    yield
    for key in keys:
        os.environ.pop(key, None)


def test_env_var_empty_string_returns_empty():
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = ""
    assert get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT") == ""


def test_env_var_default_keyword_without_fallback_raises():
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = pelorus.utils.DEFAULT_VAR_KEYWORD
    with pytest.raises(ValueError):
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT")


def test_env_var_default_keyword_with_fallback_returns_default():
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = pelorus.utils.DEFAULT_VAR_KEYWORD
    assert (
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT", "default_value") == "default_value"
    )


def test_env_var_unset_returns_none():
    assert get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT") is None


def test_env_var_custom_keyword_triggers_default():
    os.environ["PELORUS_DEFAULT_KEYWORD"] = "usepelorusdefaultvalue"
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = "usepelorusdefaultvalue"
    assert (
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT", "test_default_value")
        == "test_default_value"
    )


def test_env_var_custom_keyword_real_value_returned():
    os.environ["PELORUS_DEFAULT_KEYWORD"] = "usepelorusdefaultvalue"
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = "some_value"
    assert (
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT", "test_default_value")
        == "some_value"
    )


def test_env_var_custom_keyword_without_fallback_raises():
    os.environ["PELORUS_DEFAULT_KEYWORD"] = "usepelorusdefaultvalue"
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = "usepelorusdefaultvalue"
    with pytest.raises(ValueError):
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT")


def test_env_var_standard_keyword_not_custom_keyword():
    os.environ["PELORUS_DEFAULT_KEYWORD"] = "usepelorusdefaultvalue"
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = pelorus.utils.DEFAULT_VAR_KEYWORD
    assert (
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT", "other_default_value")
        == pelorus.utils.DEFAULT_VAR_KEYWORD
    )


def test_env_var_unset_with_fallback_returns_default():
    assert (
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT", "default_value") == "default_value"
    )

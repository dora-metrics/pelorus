import os

import pytest

import pelorus
from pelorus.utils import (
    BadAttributeKeyError,
    BadAttributePathError,
    collect_bad_attribute_path_error,
    get_env_var,
    get_nested,
)

ROOT = dict(foo=dict(bar=dict()))
PATH = "foo.bar.baz.quux"
SLICED_PATH = ["foo", "bar"]
VALUE = dict()


def test_nested_lookup_default():
    assert get_nested(ROOT, PATH, default=None) is None


def test_nested_lookup_exception():
    with pytest.raises(BadAttributePathError) as e:
        get_nested(ROOT, PATH)

    error = e.value
    print(error.message)
    assert error.path[error.path_slice] == SLICED_PATH
    assert error.value == VALUE


def test_nested_lookup_annotated():
    build_dict = {
        "apiVersion": "build.openshift.io/v1",
        "kind": "Build",
        "metadata": {
            "annotations": {
                "io.openshift.build.commit.id": "somesha",
                "io.openshift.build.commit.ref": "main/trunk",
                "io.openshift.build.source-location": "http://github.com/konveyor/pelorus",
            }
        },
    }
    assert get_nested(build_dict, "kind") == "Build"

    assert (
        get_nested(
            build_dict, "metadata.annotations", key_name="io.openshift.build.commit.id"
        )
        == "somesha"
    )


def test_nested_lookup_key_name_exception():
    build_dict = {
        "apiVersion": "build.openshift.io/v1",
        "kind": "Build",
        "metadata": {
            "annotations": {
                "io.openshift.build.commit.id": "somesha",
                "io.openshift.build.commit.ref": "main/trunk",
                "io.openshift.build.source-location": "http://github.com/konveyor/pelorus",
            }
        },
    }
    with pytest.raises(BadAttributeKeyError) as e:
        get_nested(build_dict, "metadata.annotations", key_name="commit.ids ")

    error = e.value
    assert error.message == "commit.ids is missing in metadata.annotations"


def test_nested_lookup_collect():
    errors = []

    with collect_bad_attribute_path_error(errors):
        get_nested(ROOT, PATH)

    assert len(errors) == 1
    error = errors[0]
    assert error.path[error.path_slice] == SLICED_PATH
    assert error.value == VALUE


def test_env_var_default():
    # Empty string should give us empty string
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = ""
    assert get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT") == ""

    # No default value found
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = pelorus.utils.DEFAULT_VAR_KEYWORD
    with pytest.raises(ValueError):
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT")

    # Use env variable instead of default value
    if "PELORUS_DEFAULT_KEYWORD" in os.environ:
        del os.environ["PELORUS_DEFAULT_KEYWORD"]
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = pelorus.utils.DEFAULT_VAR_KEYWORD
    assert (
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT", "default_value") == "default_value"
    )

    # If there is no env variable set, None should be returned
    if "PELORUS_TEST_ENV_VAR_DEFAULT" in os.environ:
        del os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"]
    assert get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT") is None

    # Use non standard default keyword to ensure default value is used
    os.environ["PELORUS_DEFAULT_KEYWORD"] = "usepelorusdefaultvalue"
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = "usepelorusdefaultvalue"
    assert (
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT", "test_default_value")
        == "test_default_value"
    )

    # Use env variable instead of default value
    os.environ["PELORUS_DEFAULT_KEYWORD"] = "usepelorusdefaultvalue"
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = "some_value"
    assert (
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT", "test_default_value")
        == "some_value"
    )

    # No default value found with use of custom default keyword
    os.environ["PELORUS_DEFAULT_KEYWORD"] = "usepelorusdefaultvalue"
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = "usepelorusdefaultvalue"
    with pytest.raises(ValueError):
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT")

    # Case where the env variable may be exactly the same as the default value:
    os.environ["PELORUS_DEFAULT_KEYWORD"] = "usepelorusdefaultvalue"
    os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"] = pelorus.utils.DEFAULT_VAR_KEYWORD
    assert (
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT", "other_default_value")
        == pelorus.utils.DEFAULT_VAR_KEYWORD
    )

    # If there is no env variable set, default should be returned
    if "PELORUS_DEFAULT_KEYWORD" in os.environ:
        del os.environ["PELORUS_DEFAULT_KEYWORD"]
    if "PELORUS_TEST_ENV_VAR_DEFAULT" in os.environ:
        del os.environ["PELORUS_TEST_ENV_VAR_DEFAULT"]
    assert (
        get_env_var("PELORUS_TEST_ENV_VAR_DEFAULT", "default_value") == "default_value"
    )

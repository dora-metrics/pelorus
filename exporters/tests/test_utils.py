import pytest

from pelorus.utils import (
    BadAttributePathError,
    collect_bad_attribute_path_error,
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


def test_nested_lookup_collect():
    errors = []

    with collect_bad_attribute_path_error(errors):
        get_nested(ROOT, PATH)

    assert len(errors) == 1
    error = errors[0]
    assert error.path[error.path_slice] == SLICED_PATH
    assert error.value == VALUE

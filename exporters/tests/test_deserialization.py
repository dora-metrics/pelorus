from typing import Any, Optional, Sequence, Union

import pytest
from attrs import define, field
from kubernetes.dynamic.resource import ResourceField

from pelorus.deserialization import (
    DeserializationErrors,
    FieldError,
    FieldTypeCheckError,
    InnerFieldDeserializationErrors,
    MissingFieldError,
    _extract_dict_types,
    _extract_list_type,
    _extract_optional_type,
    deserialize,
    nested,
    retain_source,
)


@define
class AttrsTestClass:
    str_: str
    int_: int
    other: Optional[list[str]] = ["test"]


@pytest.mark.parametrize(
    "type_",
    [list[int], str, set[float]],
)
def test_extract_dict_types_from_non_dict(type_: type):
    # Optional[type] breaks this function, but it is only called after parsing
    # Optional in deserialize function, so it is safe to allow this behavior
    assert _extract_dict_types(type_) is None


@pytest.mark.parametrize(
    "type_in,output",
    [(dict[str, int], (str, int)), (dict[str, list[int]], (str, list[int]))],
)
def test_extract_dict_types_from_dict(type_in: type, output: tuple[type, type]):
    assert _extract_dict_types(type_in) == output


@pytest.mark.parametrize(
    "type_",
    [dict[int, str], int, set[str]],
)
def test_extract_list_types_from_non_list(type_: type):
    assert _extract_list_type(type_) is None


@pytest.mark.parametrize(
    "type_in,output",
    [(list[int], int), (list[str], str)],
)
def test_extract_list_types_from_list(type_in: type, output: type):
    assert _extract_list_type(type_in) == output


@pytest.mark.parametrize(
    "type_",
    [
        dict[int, str],
        int,
        set[str],
        Union[str, int],
        list[float],
        Union[None, str, list[str]],
    ],
)
def test_extract_optional_types_from_non_optional(type_: type):
    assert _extract_optional_type(type_) is None


@pytest.mark.parametrize(
    "type_in,output",
    [(Optional[int], int), (Union[float, None], float), (Union[None, str], str)],
)
def test_extract_optional_types_from_optional(type_in: type, output: type):
    assert _extract_optional_type(type_in) == output


def test_deserialize_positive():
    actual = deserialize(
        dict(str_="str", int_=2), AttrsTestClass, target_name="AttrsTestClass"
    )

    assert actual.str_ == "str"
    assert actual.int_ == 2


def test_deserialize_type_error():
    with pytest.raises(DeserializationErrors) as e:
        deserialize(
            dict(str_="str", int_="string!"),
            AttrsTestClass,
            target_name="AttrsTestClass",
        )

    type_errors = e.value.subgroup(lambda e: isinstance(e, TypeError))
    assert type_errors is not None
    assert len(type_errors.exceptions) == 1
    assert isinstance(type_errors.exceptions[0], FieldTypeCheckError)


def test_deserialize_missing_error():
    with pytest.raises(DeserializationErrors) as e:
        deserialize(dict(str_="str"), AttrsTestClass, target_name="AttrsTestClass")

    missing = e.value.subgroup(lambda e: isinstance(e, MissingFieldError))
    assert missing is not None
    assert len(missing.exceptions) == 1


def test_deserialize_gives_multiple_errors_at_once():
    with pytest.raises(DeserializationErrors) as e:
        deserialize(
            dict(str_="str", int_="string!", other=[1, "2", 3]),
            AttrsTestClass,
            target_name="AttrsTestClass",
        )

    exceptions = e.value.exceptions
    assert len(exceptions) == 2
    assert isinstance(exceptions[0], FieldTypeCheckError)
    assert isinstance(exceptions[1], (InnerFieldDeserializationErrors, FieldError))


@pytest.mark.parametrize("nested_path", ["foo.bar", ("foo", "bar")])
def test_nested_field_positive(nested_path: Union[str, Sequence[str]]):
    @define
    class Nested:
        nested_int: int = field(metadata=nested(nested_path))

    actual = deserialize(dict(foo=dict(bar=2)), Nested)

    assert actual.nested_int == 2


def test_multi_nested():
    @define
    class NestedNested:
        nested_int: int = field(metadata=nested(["foo", "com.example.int"]))

    actual = deserialize({"foo": {"com.example.int": 2}}, NestedNested)

    assert actual.nested_int == 2


def test_nested_field_type_err():
    @define
    class Nested:
        nested_int: int = field(metadata=nested("foo.bar"))

    with pytest.raises(DeserializationErrors) as e:
        deserialize(dict(foo=dict(bar="string!")), Nested, target_name="Nested")

    type_errors = e.value.subgroup(lambda e: isinstance(e, TypeError))
    assert type_errors is not None
    assert len(type_errors.exceptions) == 1


def test_nested_missing():
    @define
    class Nested:
        nested_int: int = field(metadata=nested("foo.bar"))

    with pytest.raises(DeserializationErrors) as e:
        deserialize(dict(foo=dict()), Nested)

    missing = e.value.subgroup(lambda e: isinstance(e, MissingFieldError))
    assert missing is not None
    assert len(missing.exceptions) == 1


def test_multi_nested_missing():
    @define
    class Nested:
        nested_int: int = field(metadata=nested(["foo", "com", "example.int"]))

    with pytest.raises(DeserializationErrors) as e:
        deserialize(dict(foo=dict()), Nested)

    missing = e.value.subgroup(lambda e: isinstance(e, MissingFieldError))
    assert missing is not None
    assert len(missing.exceptions) == 1


def test_default():
    @define
    class Default:
        str_with_default_: str = "default"

    x = deserialize(dict(), Default)

    assert x.str_with_default_ == "default"


def test_nested_default():
    @define
    class Default:
        str_with_default_: str = field(default="default", metadata=nested("foo.bar"))

    x = deserialize(dict(foo=dict()), Default)

    assert x.str_with_default_ == "default"


def test_embedded():
    @define
    class Inner:
        str_: str

    @define
    class Outer:
        inner: Inner

    x = deserialize(dict(inner=dict(str_="str!")), Outer)

    assert x.inner.str_ == "str!"


def test_embedded_err():
    @define
    class Inner:
        int_: int

    @define
    class Outer:
        inner: Inner

    with pytest.raises(DeserializationErrors) as e:
        deserialize(dict(inner=dict(int_="str!")), Outer)

    inner_errors = e.value.subgroup(lambda e: isinstance(e, InnerFieldDeserializationErrors))
    assert inner_errors is not None
    assert len(inner_errors.exceptions) == 1


def test_inherited():
    @define
    class Parent:
        str_: str

    @define
    class Child(Parent):
        int_: int

    x = deserialize(dict(str_="str!", int_=2), Child)

    assert x.str_ == "str!"
    assert x.int_ == 2


def test_optionals():
    @define
    class Inner:
        str_: str

    @define
    class WithOption:
        maybe_str_explicit_none: Optional[str] = None
        maybe_str: Optional[str] = None
        maybe_class: Optional[Inner] = None
        maybe_dict: Optional[dict[str, str]] = None
        maybe_list: Optional[list[int]] = None

    x = deserialize(dict(maybe_str_explicit_none=None), WithOption)
    assert x.maybe_str is None


def test_optionals_error():
    @define
    class Inner:
        optional_with_default: Optional[str] = None

    @define
    class InnerOtherError:
        int_: int

    @define
    class OptionErrors:
        optional_no_default: Optional[str]
        optional_class_no_default: Optional[Inner]
        optional_other_class_error: Optional[InnerOtherError]
        optional_other_error: Optional[int]
        optional_other_error_with_default: Optional[int] = None

    with pytest.raises(DeserializationErrors) as e:
        deserialize(
            dict(
                optional_other_class_error=dict(int_="str!"),
                optional_other_error="str!",
                optional_other_error_with_default="str!",
            ),
            OptionErrors,
        )

    exc = e.value

    no_default, others = exc.by_field("optional_no_default")
    assert no_default is not None
    (no_default_err,) = no_default.exceptions
    assert isinstance(no_default_err, MissingFieldError)

    assert others is not None

    class_no_default, others = others.by_field("optional_class_no_default")
    assert class_no_default is not None
    (class_no_default_err,) = class_no_default.exceptions
    assert isinstance(class_no_default_err, MissingFieldError)

    assert others is not None

    other_class, others = others.by_field("optional_other_class_error")
    assert other_class is not None
    (other_class_err,) = other_class.exceptions
    assert isinstance(other_class_err, InnerFieldDeserializationErrors)
    (other_class_type_err,) = other_class_err.__cause__.exceptions
    assert isinstance(other_class_type_err, FieldTypeCheckError)

    assert others is not None

    other_error, others = others.by_field("optional_other_error")
    assert other_error is not None
    assert isinstance(other_error.exceptions[0], FieldTypeCheckError)
    assert len(other_class.exceptions) == 1
    assert others is not None

    other_err_with_default, others = others.by_field(
        "optional_other_error_with_default"
    )
    assert other_err_with_default is not None
    assert isinstance(other_err_with_default.exceptions[0], FieldTypeCheckError)
    assert len(other_err_with_default.exceptions) == 1

    assert others is None


def test_top_level_dict():
    x = deserialize(dict(str_="str!"), dict[str, str])
    assert x["str_"] == "str!"


def test_embedded_dict():
    @define
    class Inner:
        int_: int

    @define
    class DictHolder:
        dict_: dict[str, Inner]

    inner = dict(int_=2)
    dict_ = dict(foo=inner)
    holder = dict(dict_=dict_)

    x = deserialize(holder, DictHolder)

    assert x.dict_["foo"].int_ == 2


def test_top_level_list():
    x = deserialize([1, 2, 3], list[int])
    assert x == [1, 2, 3]


def test_embedded_list():
    @define
    class Inner:
        int_: int

    @define
    class ListHolder:
        list_: list[Inner]

    x = deserialize(dict(list_=[dict(int_=2)]), ListHolder)

    assert x.list_[0].int_ == 2


@pytest.mark.parametrize(
    "obj, structure",
    [([1, "2"], list[Any]), ({"a": "a", "1": 1}, dict[str, Any])],
)
def test_any(obj: Any, structure: type):
    # Optional[Any] not yet supported
    x = deserialize(obj, structure)
    assert x == obj


def test_resource_field():
    some_kube_resource = ResourceField(dict(foo="bar"))

    @define
    class FooHolder:
        foo: str

    x = deserialize(some_kube_resource, FooHolder)

    assert x.foo == "bar"


def test_resource_field_error():
    some_kube_resource = ResourceField(dict(foo="bar"))

    @define
    class FooHolder:
        foo: int

    with pytest.raises(DeserializationErrors) as e:
        deserialize(some_kube_resource, FooHolder)

    assert e.value.subgroup(lambda e: isinstance(e, (TypeError, FieldTypeCheckError))) is not None


def test_keeping_source():
    src = dict(foo="bar")

    @define
    class WithSource:
        foo: str
        source: Any = field(metadata=retain_source())

    x = deserialize(src, WithSource)

    assert x.foo == "bar"
    assert x.source is src

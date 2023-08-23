from typing import Any, Optional

import pytest
from attrs import define, field
from kubernetes.dynamic.resource import ResourceField

from pelorus.deserialization import (
    DeserializationErrors,
    FieldTypeCheckError,
    InnerFieldDeserializationErrors,
    MissingFieldError,
    deserialize,
    nested,
    retain_source,
)

# TODO: tests we need to add to hit non-covered areas
# - [ ] non-generic dict
# - [ ] non-generic list
# - [ ] generic set for not issubclass checks
# - [ ] completely unsupported type
# - [ ] union without None
# - [ ] class from something without getitem
# - [ ] general exception when deserializing a field? I guess nesting of any of the above
# - [ ] dict from something without getitem
# - [ ] dict with a nested thing having various errors (BadAttr, TypeCheck, Exception)...
#   will those really happen?
#   - BadAttr: won't bubble up because it only comes from a class, which would catch it
#   - typecheck: it might if we ask for an int and get a str or something, right?
#   - exception: same as above, nested non-supported type
# - [ ] or do we _not_ want to swallow exceptions like that because it's on the spec side instead of the value side?
#   we need an unsupported type error!
# - [ ] any errors on the dict, apparently?
# - [ ] list from non-iterable
# - [ ] same set of exceptions from list


def test_simple_positive():
    @define
    class Simple:
        str_: str
        int_: int

    actual = deserialize(dict(str_="str", int_=2), Simple, target_name="Simple")

    assert "str" == actual.str_
    assert 2 == actual.int_


def test_simple_type_err():
    @define
    class Int:
        int_: int

    with pytest.raises(DeserializationErrors) as e:
        deserialize(dict(int_="string!"), Int, target_name="Int")
    assert e.value.subgroup(lambda e: isinstance(e, TypeError)) is not None
    print(e.value)


def test_simple_absence():
    @define
    class Missing:
        str_: str

    with pytest.raises(DeserializationErrors) as e:
        deserialize(dict(), Missing, target_name="Missing")

    assert e.value.subgroup(lambda e: isinstance(e, MissingFieldError)) is not None
    print(e.value)


def test_nested_field_positive():
    @define
    class Nested:
        nested_int: int = field(metadata=nested("foo.bar"))

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

    assert e.value.subgroup(lambda e: isinstance(e, TypeError)) is not None
    print(e.value)


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

    print(e.value)


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


def test_any():
    x = deserialize([1, "2"], list[Any])
    assert x == [1, "2"]


def test_resource_field():
    some_kube_resource = ResourceField(dict(foo="bar"))

    @define
    class FooHolder:
        foo: str

    x = deserialize(some_kube_resource, FooHolder)

    assert x.foo == "bar"


def test_keeping_source():
    src = dict(foo="bar")

    @define
    class WithSource:
        foo: str
        source: Any = field(metadata=retain_source())

    x = deserialize(src, WithSource)

    assert x.foo == "bar"
    assert x.source is src

# Copyright Red Hat
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

"""
Declarative conversion from unstructured data to structured, type-checked data.

Useful for checking that all necessary aspects of a structure from OpenShift are present and correct.

# Supported types / conversions

S means any structured type, and U means any unstructured data that can
be converted to S.

| structured            | unstructured        |
|-----------------------|---------------------|
| attrs class¹          | Mapping[str], Any]¹ |
| list[S]               | Iterable[U]         |
| dict[str, S]          | Mapping[str, U]     |
| Any                   | Any                 |
| int, float, str, bool | themselves          |
| Optional[S]           | Optional[U]         |

¹ attrs field values may be any S type, the dict values any U type.

Attrs fields may specify a nested path using the `nested()` metadata
helper. Its semantics are the same as `pelorus.utils.get_nested`.

# Errors

For lists, dicts, and classes, errors are collected in parallel--
An error deserializing one field will not block the processing of the others.
Each error will have the name of the field it was associated with,
and also the name of the unstructured field.

Special errors exist for missing fields and failed type checks.

See the `pelorus.deserialization.errors` module for the list of error types.

# Architecture

See `README.md` in this directory.

"""
from __future__ import annotations

import typing
from typing import (
    Any,
    Iterable,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    TypeVar,
    cast,
    overload,
)

import attr
import attrs

from pelorus.deserialization.errors import (
    DeserializationErrors,
    FieldError,
    FieldTypeCheckError,
    InnerFieldDeserializationErrors,
    MissingFieldError,
    TypeCheckError,
)
from pelorus.utils import BadAttributePathError, get_nested
from pelorus.utils._attrs_compat import NOTHING

# metadata
_NESTED_PATH_KEY = "__pelorus_structure_nested_path"

T = TypeVar("T")

PRIMITIVE_TYPES: tuple[type, ...] = (int, float, str, bool)


def nested(path: str) -> dict[str, Any]:
    "Put the nested data path in a metadata dict."
    return {_NESTED_PATH_KEY: path}


def _is_attrs_class(cls: type) -> Optional[type["attr.AttrsInstance"]]:
    """
    Return the class if it is an attrs class, else None.

    This exists because `attrs.has` is not a proper TypeGuard.
    """
    return cast("type[attr.AttrsInstance]", cls) if attrs.has(cls) else None


# region: generic types

# generic types such as dict[str, int] have two parts:
# the "origin" and the "args".
# The origin in this case is `dict`, and the args are `(str, int)`.
# This lets us inspect these types properly.

# in the future, these should be made into `typing.TypeGuard`s.


def _extract_dict_types(type_: type) -> Optional[tuple[type, type]]:
    """
    If this type annotation is a dictionary-like, extract its key and value types.
    Otherwise return None.

    >>> assert _extract_dict_types(dict[str, int]) == (str, int)
    >>> assert _extract_dict_types(list[int]) is None
    """
    origin, args = typing.get_origin(type_), typing.get_args(type_)
    if origin is None:
        return None

    if not issubclass(origin, MutableMapping):
        return None

    return args[0], args[1]


def _extract_list_type(type_: type) -> Optional[type]:
    """
    If this type annotation is a list-like, extract its value type.
    Otherwise return None.

    >>> assert _extract_list_type(list[int]) == int
    >>> assert _extract_list_type(dict[str, str]) is None
    """
    origin, args = typing.get_origin(type_), typing.get_args(type_)
    if origin is None:
        return None

    if not issubclass(origin, MutableSequence):
        return None

    return args[0]


def _extract_optional_type(type_: type) -> Optional[type]:
    """
    If this type annotation is Optional[T], then returns the type T.
    Otherwise, returns None.

    >>> assert _extract_optional_type(Optional[int]) == int
    >>> assert _extract_optional_type(int) is None
    """
    # this is weird because Optional is just an alias for Union,
    # where the other entry is NoneType.
    # and in 3.10, unions with `Type1 | Type2` are a different type!
    # we'll have to handle that when adding 3.10 support.

    # it's unclear if order is guaranteed so we have to check both.
    if typing.get_origin(type_) is not typing.Union:
        return None

    args = typing.get_args(type_)

    if len(args) != 2:
        return None

    t1, t2 = args

    if issubclass(t1, type(None)):  # type: ignore
        return t2
    elif issubclass(t2, type(None)):  # type: ignore
        return t1
    else:
        return None


# endregion


@attrs.define
class _Deserializer:
    """
    A deserializer that will collect errors in parallel.

    See module docs for more details.
    """

    # The deserializer uses a simple "dispatch" pattern.
    # The target type is checked to see if it is any of the supported primitive types.
    # If it is an attrs class, it will deserialize each field by their type,
    # supporting the "nested" pattern from `get_nested`.

    # Because of nested fields, dicts, and lists, deserialization is recursive.
    # The "path" is kept track of for error messages.
    # See `README.md` for more details.

    unstructured_data_path: list[str] = attrs.field(factory=list, init=False)
    "Where we are within the unstructured data."
    structured_field_name_path: list[str] = attrs.field(factory=list, init=False)
    "Where we are within the structured data."

    def deserialize(
        self, src: Any, target_type: type[T], src_name: str = "", target_name: str = ""
    ) -> T:
        """
        Deserialize the unstructured src data into the given target type.
        src_name and target_name are used for helpful error messages,
        and will default to the names of the argument types.
        """
        target_name = target_name if target_name else str(target_type)

        src_name = src_name if src_name else type(src).__name__

        self.structured_field_name_path.append(target_name)
        self.unstructured_data_path.append(src_name)
        try:
            return self._deserialize(src, target_type)
        finally:
            self.unstructured_data_path.pop()
            self.structured_field_name_path.pop()

    @overload
    def _deserialize(self, src: Any, target_type: type[T]) -> T:
        ...

    @overload
    def _deserialize(self, src: Any, target_type: type[Optional[T]]) -> Optional[T]:
        ...

    def _deserialize(self, src: Any, target_type) -> Optional[Any]:
        """
        Dispatch to a deserialization method based on target_type,
        with some pre-checks for the src.
        """
        # lying a bit here with the type signature, because things
        # like Optional[str] are not "types", technically.
        # I don't know the right way to type that though.

        if target_type is Any:
            return src

        # must test "non-classes" first, because they're not regarded as "types".
        if (optional_alt := _extract_optional_type(target_type)) is not None:
            return self._deserialize_optional(src, optional_alt)

        if issubclass(target_type, PRIMITIVE_TYPES):
            return self._deserialize_primitive(src, target_type)

        if attrs.has(target_type):
            if isinstance(src, Mapping):
                # assuming it has str key types.
                return self._deserialize_attrs_class(src, target_type)
            else:
                raise TypeCheckError(Mapping, src)

        if (dict_types := _extract_dict_types(target_type)) is not None:
            if isinstance(src, Mapping):
                # assuming it has str key types.
                return self._deserialize_dict(src, dict_types[1])
            else:
                raise TypeCheckError(Mapping, src)

        if (list_member_type := _extract_list_type(target_type)) is not None:
            if isinstance(src, Iterable):
                return self._deserialize_list(src, list_member_type)
            else:
                raise TypeCheckError(Iterable, src)

        raise TypeError(f"Unsupported type for deserialization: {target_type.__name__}")

    def _deserialize_optional(self, src: Any, optional_alt: type[T]) -> Optional[T]:
        """
        Deserialize an optional type, handling the None case properly.
        """
        if src is None:
            return None  # type: ignore
        return self._deserialize(src, optional_alt)

    def _deserialize_field(self, src: Mapping[str, Any], field: attrs.Attribute):
        """
        Deserialize a field within an attrs class.
        """
        assert field.type is not None, f"{field.name} is missing a type"

        nested: Optional[str] = field.metadata.get(_NESTED_PATH_KEY)

        path = nested if nested else field.name

        self.structured_field_name_path.append(field.name)
        self.unstructured_data_path.append(path)
        try:
            value = get_nested(src, path, name=self.unstructured_data_path[-1])
            return self._deserialize(value, field.type)
        except BadAttributePathError:
            # the value itself is missing.
            if field.default is not NOTHING:
                return NOTHING
            else:
                raise
        finally:
            self.unstructured_data_path.pop()
            self.structured_field_name_path.pop()

    def _deserialize_attrs_class(self, src: Mapping[str, Any], to: type[T]) -> T:
        "Initialize an attrs class field-by-field."
        cls = _is_attrs_class(to)
        assert cls is not None, f"class was not an attrs class: {to.__name__}"

        field_errors = []
        class_kwargs = {}

        field: attrs.Attribute
        for field in attrs.fields(cls):
            try:
                # child will handle names because it has nested info
                value = self._deserialize_field(src, field)

                if value is not NOTHING:
                    class_kwargs[field.name] = value
            except BadAttributePathError as e:
                field_errors.append(MissingFieldError(field.name, e))
            except TypeCheckError as e:
                field_errors.append(FieldTypeCheckError(field.name, e))
            except DeserializationErrors as e:
                # field was an attrs class itself
                err = InnerFieldDeserializationErrors(field.name, e)
                field_errors.append(err)
            except Exception as e:
                err = FieldError(field.name, e)
                field_errors.append(err)

        if not field_errors:
            return cls(**class_kwargs)  # type: ignore
        else:
            raise DeserializationErrors(
                field_errors,
                target_name=self.structured_field_name_path[-1],
                src_name=self.unstructured_data_path[-1],
            )

    def _deserialize_dict(
        self, src: Mapping[str, Any], target_value_type: type[T]
    ) -> dict[str, T]:
        """
        Deserialize a dictionary, deserializing its values to the target type.
        """
        dict_ = {}
        errors = []
        for key, value in src.items():
            # it's a little bit weird, because a dict is both structured and unstructured.
            self.unstructured_data_path.append(key)
            self.structured_field_name_path.append(key)

            try:
                value = self._deserialize(value, target_value_type)
                dict_[key] = value
            except BadAttributePathError as e:
                errors.append(MissingFieldError(key, e))
            except TypeCheckError as e:
                errors.append(FieldTypeCheckError(key, e))
            except Exception as e:
                err = FieldError(key, e)
                errors.append(err)
            finally:
                self.unstructured_data_path.pop()
                self.structured_field_name_path.pop()

        if not errors:
            return dict_
        else:
            raise DeserializationErrors(
                errors,
                src_name=self.unstructured_data_path[-1],
                target_name=self.structured_field_name_path[-1],
            )

    def _deserialize_list(
        self, src: Iterable[Any], target_value_type: type[T]
    ) -> list[T]:
        """
        Deserialize a list, deserializing its values to the target type.
        """
        list_ = []
        errors = []

        for i, item in enumerate(iter(src)):
            i = str(i)
            try:
                # it's a little bit weird, because a list is both structured and unstructured.
                self.unstructured_data_path.append(i)
                self.structured_field_name_path.append(i)

                value = self._deserialize(item, target_value_type)
                list_.append(value)
            except BadAttributePathError as e:
                errors.append(MissingFieldError(i, e))
            except TypeCheckError as e:
                errors.append(FieldTypeCheckError(i, e))
            except Exception as e:
                err = FieldError(i, e)
                errors.append(err)
            finally:
                self.unstructured_data_path.pop()
                self.structured_field_name_path.pop()

        if not errors:
            return list_
        else:
            raise DeserializationErrors(
                errors,
                src_name=self.unstructured_data_path[-1],
                target_name=self.structured_field_name_path[-1],
            )

    def _deserialize_primitive(self, value: Any, target_type: type[T]) -> T:
        "Deserialize a primitive by checking it is the target type."
        if isinstance(value, target_type):
            return value
        else:
            raise TypeCheckError(target_type, value)


def deserialize(
    src: Any, target_type: type[T], src_name: str = "", target_name: str = ""
) -> T:
    """
    Deserialize any supported type (see module docs) from unstructured data.
    src_name and target_name are used for helpful error messages,
    and will default to the names of the argument types.
    """
    return _Deserializer().deserialize(src, target_type, src_name, target_name)

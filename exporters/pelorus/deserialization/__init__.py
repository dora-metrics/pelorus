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
    Literal,
    Mapping,
    MutableSequence,
    NamedTuple,
    Optional,
    Sequence,
    TypeVar,
    Union,
    get_type_hints,
    overload,
)

import attr
import attrs
from typing_extensions import TypeGuard

from pelorus.deserialization.errors import (
    DeserializationErrors,
    FieldError,
    FieldTypeCheckError,
    InnerFieldDeserializationErrors,
    MissingFieldError,
    TypeCheckError,
)
from pelorus.utils import BadAttributePathError, format_path, get_nested, split_path
from pelorus.utils._attrs_compat import NOTHING

# metadata
_NESTED_PATH_KEY = "__pelorus_structure_nested_path"
_RETAIN_SOURCE_KEY = "__pelorus_structure_retain_source"

T = TypeVar("T")

PRIMITIVE_TYPES: tuple[type, ...] = (int, float, str, bool)


def nested(path: Union[str, Sequence[str]]) -> dict[str, Sequence[str]]:
    """
    Put the nested data path in a metadata dict.
    Like get_nested, use a list if a path segment has a dot in it.
    """
    return {_NESTED_PATH_KEY: split_path(path)}


def retain_source(retain: bool = True) -> dict[str, bool]:
    """
    Retain the source of the deserialization in this field.
    """
    return {_RETAIN_SOURCE_KEY: retain}


# python has some magic to make classes work with `issubclass` and instances work with `isinstance`,
# even if they don't actually inherit from them. Some so-called "abstract base classes" just check
# for the presence of certain methods. Cool!
# However, some of them don't support that, for reasons outlined in their docs (see the first section):
# https://docs.python.org/3.11/library/collections.abc.html

# thus, we need to make our own checks. These have the same downsides as in the docs,
# but they're "good enough". "Practicality beats purity".

# we need this for mappings specifically, because a kubernetes.dynamic.resource.ResourceField has
# __getitem__, which is actually all we care about.


def _type_has_getitem(type_: type) -> bool:
    "See if this type has a getitem method (supports item[key])"
    return hasattr(type_, "__getitem__")


# region: attrs fixes

# type annotations can be represented as the types themselves, or as strings.
# attrs seems to use strings for fields in inherited classes, which can break
# things for us. This may be a bug that has to be fixed for them.
# Until then, here's a small alternative.


def _is_attrs_class(cls: type) -> TypeGuard[type["attr.AttrsInstance"]]:
    """
    Return the class if it is an attrs class, else None.

    This exists because `attrs.has` is not a proper TypeGuard.
    """
    return attrs.has(cls)


class Field(NamedTuple):
    """
    Relevant field information for an attrs class.
    """

    name: str
    type: type
    default: Union[Any, Literal[NOTHING]]
    metadata: dict[Any, Any]


def _fields(cls: type["attr.AttrsInstance"]) -> Iterable[Field]:
    "Get all field information for this attrs class."
    hints = get_type_hints(cls)
    attrs_fields = attrs.fields(cls)
    for field in attrs_fields:
        yield Field(
            field.name,
            hints[field.name],
            default=field.default,
            metadata=field.metadata,
        )


# endregion

# region: generic types

# generic types such as dict[str, int] have two parts:
# the "origin" and the "args".
# The origin in this case is `dict`, and the args are `(str, int)`.
# This lets us inspect these types properly.


def _extract_dict_types(type_: type) -> Optional[tuple[type, type]]:
    """
    If this type annotation is a dictionary-like, extract its key and value types.
    Otherwise return None.

    dictionary-like is defined as "has __getitem__ and two type arguments".
    """
    origin, args = typing.get_origin(type_), typing.get_args(type_)
    if origin is None:
        return None

    if not _type_has_getitem(type_):
        return None
    if len(args) != 2:
        return None

    return args[0], args[1]


def _extract_list_type(type_: type) -> Optional[type]:
    """
    If this type annotation is a list-like, extract its value type.
    Otherwise return None.
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

    unstructured_data_path: list[Union[str, Sequence[str]]] = attrs.field(
        factory=list, init=False
    )
    """
    Where we are within the unstructured data.
    If the name is a sequence, this means that there was a `get_nested` path that had dots in it,
    so the path must be separated to differentiate the dots.
    """
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
            if _type_has_getitem(type(src)):
                # assuming it has str key types.
                return self._deserialize_attrs_class(src, target_type)
            else:
                raise TypeCheckError("Mapping", src)

        if (dict_types := _extract_dict_types(target_type)) is not None:
            if _type_has_getitem(type(src)):
                # assuming it has str key types.
                return self._deserialize_dict(src, dict_types[1])
            else:
                raise TypeCheckError("Mapping", src)

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
            return None
        return self._deserialize(src, optional_alt)

    def _deserialize_field(self, src: Mapping[str, Any], field: Field):
        """
        Deserialize a field within an attrs class.
        """
        if field.metadata.get(_RETAIN_SOURCE_KEY, False):
            return src

        nested: Optional[Sequence[str]] = field.metadata.get(_NESTED_PATH_KEY)

        path = nested if nested else (field.name,)

        self.structured_field_name_path.append(field.name)
        self.unstructured_data_path.append(path)
        try:
            value = get_nested(src, path)
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
        assert _is_attrs_class(to), f"class was not an attrs class: {to.__name__}"

        field_errors = []
        class_kwargs = {}

        for field in _fields(to):
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
            return to(**class_kwargs)  # type: ignore
        else:
            unstructured_src = self.unstructured_data_path[-1]
            src_name = (
                unstructured_src
                if isinstance(unstructured_src, str)
                else format_path(unstructured_src)
            )
            raise DeserializationErrors(
                field_errors,
                target_name=self.structured_field_name_path[-1],
                src_name=src_name,
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
            unstructured_src = self.unstructured_data_path[-1]
            src_name = (
                unstructured_src
                if isinstance(unstructured_src, str)
                else format_path(unstructured_src)
            )
            raise DeserializationErrors(
                errors,
                src_name=src_name,
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
            unstructured_src = self.unstructured_data_path[-1]
            src_name = (
                unstructured_src
                if isinstance(unstructured_src, str)
                else format_path(unstructured_src)
            )
            raise DeserializationErrors(
                errors,
                src_name=src_name,
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

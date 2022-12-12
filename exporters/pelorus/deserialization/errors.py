from __future__ import annotations

from io import StringIO
from typing import Any, Generic, Optional, Sequence, TypeVar, Union

from exceptiongroup import ExceptionGroup

from pelorus.utils import BadAttributePathError


class DeserializationError(Exception):
    "An error that occurred during Deserialization."
    pass


Exc = TypeVar("Exc", bound=Optional[Exception])


class FieldError(DeserializationError, Generic[Exc]):
    "An error that relates to a single field."
    __cause__: Exc

    def __init__(self, field_name: str, cause: Exc):
        self.field_name = field_name
        self.__cause__ = cause
        if self.__cause__ is not None:
            self.message = f"{self.field_name}: {self.__cause__}"
        else:
            self.message = f"{self.field_name} error"

        super().__init__(self.message)


class MissingFieldError(FieldError[Optional[BadAttributePathError]]):
    "A field that is missing."
    pass


class MissingFieldWithMultipleSourcesError(MissingFieldError):
    "A field that was missing, that was not present multiple alternative sources."

    # TODO: kind of an exception group in its own right, but do we care?
    # because each fallback could have its own cause, etc...

    def __init__(self, field_name: str, sources: Sequence[str]):
        # overriding FieldError's init a bit for better message handling.
        self.field_name = field_name
        self.__cause__ = None
        self.sources = sources

        self.message = f"{self.field_name} was not present in any of the following sources: {', '.join(self.sources)}"


class TypeCheckError(TypeError):
    "A value that failed a type check."

    def __init__(self, expected_type: Union[type, str], actual_value: Any):
        self.expected_type = expected_type
        self.actual_value = actual_value
        # "real" types (like a dict) / classes have a __name__.
        # things like typing.Mapping have a _name instead for some reason.
        # funnily enough, collections.abc.Mapping has a __name__. Weird!
        if isinstance(expected_type, str):
            expected_name = expected_type
        else:
            expected_name = (
                getattr(expected_type, "__name__", None)
                or getattr(expected_type, "_name", None)
                or str(expected_type)  # fallback just in case of true weirdness.
            )
        msg = (
            f"needed a {expected_name},"
            f" but got an instance of <{self.actual_type.__name__}>: {self.actual_value}"
        )
        super().__init__(msg)

    @property
    def actual_type(self):
        return type(self.actual_value)


class FieldTypeCheckError(FieldError, TypeError):
    "A field that did not type-check correctly."
    __cause__: TypeCheckError

    def __init__(self, field_name: str, cause: TypeCheckError):
        super().__init__(field_name, cause)


class DeserializationErrors(ExceptionGroup[DeserializationError], DeserializationError):
    "Any number of deserialization errors."
    src_name: str
    target_name: str

    def __new__(
        cls,
        errors: Sequence[DeserializationError],
        *,
        src_name: str = "",
        target_name: str = "",
    ):
        if len(errors) > 1:
            msg = "Errors while deserializing"
        else:
            msg = "Error while deserializing"

        if target_name:
            msg += f" {target_name}"

        if src_name:
            msg += f" from {src_name}"

        self = super().__new__(DeserializationErrors, msg, errors)

        self._message = msg  # workaround, see __init__

        # for some reason, pyright rejects assigning in __new__
        self.src_name = src_name  # type: ignore
        self.target_name = target_name  # type: ignore

        return self

    # workaround due to https://github.com/agronholm/exceptiongroup/issues/46
    def __init__(
        self,
        errors: Sequence[DeserializationError],
        *,
        src_name: str = "",
        target_name: str = "",
    ):
        super().__init__(self._message, errors)

    def derive(self, excs: Sequence[DeserializationError]):
        return DeserializationErrors(
            excs, src_name=self.src_name, target_name=self.target_name
        )

    def by_field(
        self, field_name: str
    ) -> tuple[Optional[DeserializationErrors], Optional[DeserializationErrors]]:
        """
        Split into two groups: field errors matching the given field name,
        and all others.

        Similar behavior to `ExceptionGroup.split`.
        """
        # these can technically never be none at the same time, but the caller
        # has to handle it as if that's possible anyway.
        def matches(err):
            return isinstance(err, FieldError) and err.field_name == field_name

        with_field = tuple(err for err in self.exceptions if matches(err))
        without_field = tuple(err for err in self.exceptions if not matches(err))

        return (
            DeserializationErrors(
                with_field, src_name=self.src_name, target_name=self.target_name
            )
            if with_field
            else None,
            DeserializationErrors(
                without_field, src_name=self.src_name, target_name=self.target_name
            )
            if without_field
            else None,
        )

    def __str__(self):
        "More user-friendly error information."
        buf = StringIO()
        print(self.message, ":", sep="", file=buf)
        for err in self.exceptions:
            for line in str(err).splitlines():
                print(2 * " ", line, sep="", file=buf)

        return buf.getvalue()


class InnerFieldDeserializationErrors(FieldError[DeserializationErrors]):
    """
    A field which was a nested structure (dict, list, attrs class)
    had errors.

    While this is called "errors", it is not an exception group.
    Rather, it wraps one.
    """

    pass

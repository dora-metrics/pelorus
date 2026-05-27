import enum
from typing import Any, Mapping, Optional

from attrs import Attribute

from pelorus.config.common import Metadata

REDACT_WORDS = {"pass", "token", "key", "cred", "secret", "auth"}
"""Words that trigger automatic redaction when found in a field name (case-insensitive)."""

_SHOULD_LOG = "__pelorus_config_log"


class Log(enum.Enum):
    LOG = enum.auto()
    """
    The field's key and value should be logged.
    """
    REDACT = enum.auto()
    """
    The field's key should be logged, and the value replaced by `REDACTED`.
    """
    SKIP = enum.auto()
    """
    The field will be skipped from logging entirely.
    """


LOG = Log.LOG
REDACT = Log.REDACT
SKIP = Log.SKIP


def log(should: Log) -> Metadata:
    """
    Configure a field to be explicitly logged, redacted, or skipped.
    """
    return {_SHOULD_LOG: should}


def _get_log_meta(meta: Mapping[str, Any]) -> Optional[Log]:
    return meta.get(_SHOULD_LOG)


def _should_log(field: Attribute) -> Log:
    """
    Determine how a field should be logged: LOG, REDACT, or SKIP.

    Explicitly marked fields use their configured value.
    Private fields (starting with '_') are skipped entirely.
    Fields with sensitive words (members of REDACT_WORDS) are redacted.
    All other fields are logged normally.
    """
    should_log = _get_log_meta(field.metadata)
    if should_log is not None:
        return should_log

    is_private = field.name.startswith("_")
    if is_private:
        return Log.SKIP

    should_be_redacted = any(word in field.name.lower() for word in REDACT_WORDS)
    if should_be_redacted:
        return Log.REDACT

    return Log.LOG


__all__ = ["Log", "REDACT_WORDS", "log", "LOG", "REDACT", "SKIP"]

import enum
from typing import Any, Mapping, Optional

from attrs import Attribute

from pelorus.config.common import Metadata

REDACT_WORDS = {"pass", "token", "key", "cred", "secret", "auth"}
"""
Variables containing these words are not logged by default, nor are attributes starting with an underscore.
"""

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
    A field should NOT be logged if it explicitly marked as such,
    or contains a word that implies it is sensitive (members of REDACT_WORDS).
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

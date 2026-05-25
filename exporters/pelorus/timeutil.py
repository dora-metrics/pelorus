"""
Utilities to handle time correctly.

Note: `parse_assuming_utc`, `parse_tz_aware`, and `parse_guessing_timezone_DYNAMIC`
will _always_ produce timezone-aware objects,
which are necessary for correctness with `astimezone(tz)`, `timestamp()`, and other methods.
"""
import time as _time

from datetime import datetime, timedelta, timezone

_ISO_ZULU_FMT = "%Y-%m-%dT%H:%M:%SZ"

# Time after which metrics will not be accepted (used by deploytime, webhook, etc.)
# Override with PELORUS_TIMESTAMP_THRESHOLD_MINUTES env var for seeding historical data
import os as _os

_threshold_raw = _os.environ.get("PELORUS_TIMESTAMP_THRESHOLD_MINUTES", "30")
try:
    METRIC_TIMESTAMP_THRESHOLD_MINUTES = int(_threshold_raw)
except ValueError:
    raise ValueError(
        f"PELORUS_TIMESTAMP_THRESHOLD_MINUTES must be an integer, got: {_threshold_raw!r}"
    )
if METRIC_TIMESTAMP_THRESHOLD_MINUTES < 1:
    raise ValueError(
        f"PELORUS_TIMESTAMP_THRESHOLD_MINUTES must be >= 1, got: {METRIC_TIMESTAMP_THRESHOLD_MINUTES}"
    )
_METRIC_TIMESTAMP_THRESHOLD_SECONDS = METRIC_TIMESTAMP_THRESHOLD_MINUTES * 60


def is_zone_aware(d: datetime) -> bool:
    """
    Is the datetime object aware of its timezone/offset?
    See https://docs.python.org/3/library/datetime.html#determining-if-an-object-is-aware-or-naive
    """
    return d.tzinfo is not None and d.tzinfo.utcoffset(d) is not None


def parse_assuming_utc(timestring: str, format: str) -> datetime:
    """
    Parses assuming that the timestring is UTC only.
    The format must not include timezone information.
    The parsed datetime is returned as timezone-aware (UTC).
    Otherwise, a ValueError will be raised.
    """
    parsed = datetime.strptime(timestring, format)
    if is_zone_aware(parsed):
        raise ValueError(
            f"Tried to assume UTC with a timezone-aware time format of {format}"
        )
    else:
        return parsed.replace(tzinfo=timezone.utc)


def parse_assuming_utc_with_fallback(
    timestring: str, format: str, format_fallback: str
) -> datetime:
    """
    Parse timestring with fallback case.

    Try to parse timestring (UTC only) with `format`, if it fails, try to parse
    it again, using `format_fallback`.

    Parameters
    ----------
    timestring : str
        String to be parsed, in UTC format.
    format : str
        Default format.
    format_fallback : str
        Fallback format.

    Returns
    -------
    datetime
        Parsed timestring.
    """
    try:
        return parse_assuming_utc(timestring, format)
    except ValueError:
        return parse_assuming_utc(timestring, format_fallback)


def parse_tz_aware(timestring: str, format: str) -> datetime:
    """
    Parses a timestring that includes its timezone information.
    The format must include timezone information, so the parsed result is aware.
    Otherwise, a ValueError will be raised.
    """
    parsed = datetime.strptime(timestring, format)
    if not is_zone_aware(parsed):
        raise ValueError(
            f"Tried to be timezone-aware with timezone-naive format of {format}"
        )
    else:
        return parsed.astimezone(timezone.utc)


def parse_guessing_timezone_DYNAMIC(timestring: str, format: str) -> datetime:
    """
    Assumes the timezone is correct if the format makes it aware, but otherwise assumes UTC.

    This should only be used in a user-provided case.\
    Otherwise, use one of the other methods to validate that an API contract hasn't been broken.
    """
    parsed = datetime.strptime(timestring, format)
    if is_zone_aware(parsed):
        return parsed
    else:
        return parsed.replace(tzinfo=timezone.utc)


def to_epoch_from_string(timestring: str) -> datetime:
    """
    Convert a string containing a Unix epoch timestamp to a datetime object.

    The timestring must be a 10-digit epoch timestamp (seconds since 1970-01-01),
    optionally followed by a fractional part (which is discarded).
    Raises ValueError if the string is not a valid 10-digit epoch.
    """
    epoch_date_time = timestring.split(".")[0]
    # Try to convert to an EPOCH, but only if it's 10 digit
    if len(epoch_date_time) != 10:
        raise ValueError(
            f"Tried to get epoch from not allowed string length: {timestring}"
        )
    else:
        return datetime.fromtimestamp(int(epoch_date_time), tz=timezone.utc)


def second_precision(dt: datetime) -> datetime:
    """
    Change the datetime to have second precision (removing microseconds).
    Useful for logging.
    There are also places in legacy code that do this (via formatting and then re-parsing),
    but those usages should be scrutinized.
    """
    return dt.replace(microsecond=0)


def to_iso(dt: datetime) -> str:
    """
    Formats a datetime to an ISO string with a hard-coded Z.
    If the input is naive, a ValueError is raised.
    """
    if not is_zone_aware(dt):
        raise ValueError(
            "tried to serialize datetime with hard-coded Z but it was timezone naive"
        )

    return dt.astimezone(timezone.utc).strftime(_ISO_ZULU_FMT)


def is_out_of_date(timestring: str) -> bool:
    """
    Helper function, which allows to filter out metrics which are older than
    the accepted time. This is to ensure Prometheus will not try to scrape too
    old metrics.
    """
    epoch_dt = to_epoch_from_string(timestring)
    return (datetime.now(timezone.utc) - epoch_dt).total_seconds() > _METRIC_TIMESTAMP_THRESHOLD_SECONDS


def is_out_of_date_timestamp(timestamp: float) -> bool:
    """
    Like is_out_of_date, but takes a Unix timestamp directly
    instead of a string, avoiding unnecessary conversions.
    """
    return _time.time() - timestamp > _METRIC_TIMESTAMP_THRESHOLD_SECONDS

"""
Utilities to handle time correctly.

Note: `parse_assuming_utc`, `parse_tz_aware`, and `parse_guessing_timezone_DYNAMIC`
will _always_ produce timezone-aware objects,
which are necessary for correctness with `astimezone(tz)`, `timestamp()`, and other methods.
"""
from datetime import datetime, timedelta, timezone

_ISO_ZULU_FMT = "%Y-%m-%dT%H:%M:%SZ"

# Time after which metrics for the deploytime exporter will not be accepted
METRIC_TIMESTAMP_THRESHOLD_MINUTES = 30


def is_zone_aware(d: datetime) -> bool:
    """
    Is the datetime object aware of its timezone/offset?
    See https://docs.python.org/3/library/datetime.html#determining-if-an-object-is-aware-or-naive
    """
    return d.tzinfo is not None and d.tzinfo.utcoffset(d) is not None


def parse_assuming_utc(timestring: str, format: str) -> datetime:
    """
    Parses assuming that the timestring is UTC only.
    This means it _must_ be naive, e.g. has no zone/offset parsing in the format.
    Otherwise, a ValueError will be raised.
    """
    parsed = datetime.strptime(timestring, format)
    if is_zone_aware(parsed):
        raise ValueError(
            f"Tried to assume UTC with a timezone-aware time format of {format}"
        )
    else:
        return parsed.replace(tzinfo=timezone.utc)


def parse_tz_aware(timestring: str, format: str) -> datetime:
    """
    Parses a timestring that includes its timezone information.
    That means it _must not_ be naive, e.g. has proper zone/parsing in the format.
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
    Otherwise, use one of the other methods to validate that an API contract hasn't been borken.
    """
    parsed = datetime.strptime(timestring, format)
    if is_zone_aware(parsed):
        return parsed
    else:
        return parsed.replace(tzinfo=timezone.utc)


def to_epoch_from_string(timestring: str) -> datetime:
    """
    It's really EPOCH to EPOCH conversion with datetime return object.

    If timestring matches expected EPOCH format a proper datetime object is returned,
    otherwise raises ValueError and consumer of this function probably want's to use
    other format of timestamp.
    """
    epoch_date_time = timestring.split(".")[0]
    # Try to convert to an EPOCH, but only if it's 10 digit
    if len(epoch_date_time) != 10:
        raise ValueError(
            f"Tried to get epoch from not allowed string length: {timestring}"
        )
    else:
        return datetime.fromtimestamp(int(epoch_date_time))


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
    Helper function, which allows to filter out metrics which are older then
    the accepted time. This is to ensure Prometheus will not try to scrape too
    old metrics.
    """
    return datetime.now() - to_epoch_from_string(timestring) > timedelta(
        minutes=METRIC_TIMESTAMP_THRESHOLD_MINUTES
    )

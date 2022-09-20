from datetime import datetime, timedelta, timezone

import provider_common.github as github
from pelorus.timeutil import (
    parse_assuming_utc,
    parse_guessing_timezone_DYNAMIC,
    parse_tz_aware,
)


def test_parse_hard_utc():
    FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    TIMESTRING = "2020-06-27T03:17:8Z"
    UNIX = 1593227828
    DATETIME = datetime(2020, 6, 27, 3, 17, 8, tzinfo=timezone.utc)

    actual_start = parse_assuming_utc(TIMESTRING, FORMAT)
    assert actual_start == DATETIME

    actual_start_unix = actual_start.timestamp()
    assert actual_start_unix == UNIX


def test_parse_tz_aware():
    FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"
    UTC_MINUS_5 = timezone(timedelta(hours=-5))

    TIMESTRING = "2020-06-27T03:17:08.00000-0500"
    UNIX = 1593245828
    DATETIME = datetime(2020, 6, 27, 3, 17, 8, tzinfo=UTC_MINUS_5)

    actual_start = parse_tz_aware(TIMESTRING, FORMAT)
    assert actual_start == DATETIME

    actual_start_unix = actual_start.timestamp()
    assert actual_start_unix == UNIX


def test_parse_tz_aware_diff_timezones():
    FORMAT = "%Y-%m-%dT%H:%M:%S%z"

    UTC_MINUS_4 = timezone(timedelta(hours=-4))
    UTC_PLUS_2 = timezone(timedelta(hours=2))

    UNIX = 1663715897

    TIMESTRING_IN_NY = "2022-09-20T19:18:17-0400"
    DATETIME_NY = datetime(2022, 9, 20, 19, 18, 17, tzinfo=UTC_MINUS_4)

    TIMESTRING_IN_PL = "2022-09-21T01:18:17+0200"
    DATETIME_PL = datetime(2022, 9, 21, 1, 18, 17, tzinfo=UTC_PLUS_2)

    actual_ny = parse_tz_aware(TIMESTRING_IN_NY, FORMAT)
    actual_pl = parse_tz_aware(TIMESTRING_IN_PL, FORMAT)

    assert DATETIME_NY == DATETIME_PL

    assert actual_ny == DATETIME_NY
    assert actual_pl == DATETIME_PL
    assert actual_ny == actual_pl

    assert actual_ny.timestamp() == UNIX
    assert actual_pl.timestamp() == UNIX


def test_dynamic_parsing_aware():
    AWARE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
    UTC_MINUS_4 = timezone(timedelta(hours=-4))

    UNIX = 1663715897

    TIMESTRING = "2022-09-20T19:18:17-0400"
    DATETIME = datetime(2022, 9, 20, 19, 18, 17, tzinfo=UTC_MINUS_4)

    actual_parsed = parse_guessing_timezone_DYNAMIC(TIMESTRING, AWARE_FORMAT)

    assert actual_parsed == DATETIME

    assert actual_parsed.timestamp() == UNIX


def test_dynamic_parsing_assumed():
    ASSUMING_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    UNIX = 1663715897

    TIMESTRING = "2022-09-20T23:18:17Z"
    DATETIME = datetime(2022, 9, 20, 23, 18, 17, tzinfo=timezone.utc)

    actual_parsed = parse_guessing_timezone_DYNAMIC(TIMESTRING, ASSUMING_FORMAT)

    assert actual_parsed == DATETIME

    assert actual_parsed.timestamp() == UNIX


def test_github():
    TIMESTRING = "2022-05-11T21:50:08Z"
    EXPECTED_UNIX = 1652305808

    actual_unix = github.parse_datetime(TIMESTRING).timestamp()

    assert actual_unix == EXPECTED_UNIX

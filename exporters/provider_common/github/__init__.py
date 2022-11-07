"""
A small subset of a GitHub API client. Provides:
- a rate-limit respecting and logging HTTP client
- tools to make pagination trivial
- error types to handle errors from the API separately
- a consistent way to parse their date format
"""
from datetime import datetime

from pelorus.timeutil import parse_assuming_utc

from .errors import GitHubError, GitHubRateLimitError
from .pagination import PageResponse, paginate, paginate_items
from .rate_limit import RateLimitingClient

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_datetime(datetime_str: str) -> datetime:
    """
    Parse the ISO 8601 datetime string used in all github responses:
    https://docs.github.com/en/rest/overview/resources-in-the-rest-api#schema

    The datetime will be timezone-aware and in UTC.

    Will raise a ValueError if it doesn't match the expected format.
    """
    return parse_assuming_utc(datetime_str, format=_DATETIME_FORMAT)


__all__ = [
    "parse_datetime",
    "PageResponse",
    "paginate",
    "paginate_items",
    "RateLimitingClient",
    "GitHubError",
    "GitHubRateLimitError",
]

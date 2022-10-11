"""
An HTTP client that respects GitHub's rate limiting:
https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import NamedTuple, Optional

import requests

from .errors import GitHubRateLimitError

# The maximum number of requests you're permitted to make per hour.
RATELIMIT_LIMIT_HEADER = "x-ratelimit-limit"
# The number of requests remaining in the current rate limit window.
RATELIMIT_REMAINING_HEADER = "x-ratelimit-remaining"
# The time at which the current rate limit window resets in UTC epoch seconds.
RATELIMIT_RESET_HEADER = "x-ratelimit-reset"


class RateLimit(NamedTuple):
    """
    The rate limit information from a response from the GitHub API.

    Rate limit headers are provided on each response, regardless
    of its success or failure. Thus this data doesn't necessarily
    mean it's an error!

    If the `message` field is present, _then_ it's from an error.
    """

    limit: int
    remaining: int
    reset_time: datetime
    """
    The time at which our `remaining` count will be reset to `limit`.
    """
    message: Optional[str]
    """
    The rate limit error message, or `None` if this did not come
    from a rate limit error.
    """

    @classmethod
    def from_response(cls, response: requests.Response) -> RateLimit:
        """
        Create from a GitHub API response.
        """
        rate_limit = int(response.headers[RATELIMIT_LIMIT_HEADER])
        remaining_requests = int(response.headers[RATELIMIT_REMAINING_HEADER])

        reset_time = response.headers[RATELIMIT_RESET_HEADER]
        reset_time = datetime.fromtimestamp(float(reset_time), timezone.utc)

        message = None
        # GitHub uses 403 Forbidden instead of
        # 429 Too Many Requests for some reason.
        if response.status_code == 403:
            json = response.json()
            if "rate limit" in json["message"]:
                # JSON Error responses always have a message,
                # in this case mentioning the rate limit.
                message = json["message"]
            # If the rate limit is not mentioned in the response,
            # it must be an error for some other reason,
            # and we let the caller handle that.

        return cls(rate_limit, remaining_requests, reset_time, message)

    def is_limited_at(self, now: datetime):
        """
        Are we still rate limited at the given datetime?
        """
        if self.remaining:
            return False
        return self.reset_time > now

    def make_error(self, response: Optional[requests.Response]) -> GitHubRateLimitError:
        """
        response will either be the response that triggered a rate limit error,
        or None if this is for an older rate limit that was checked before sending.
        """
        return GitHubRateLimitError(
            response,
            self.message if self.message else "Would hit rate limit",
            reset_time=self.reset_time,
        )


def _log_ratelimit(rate_limit: RateLimit):
    """
    Log ratelimit header values as a debug message,
    or an error if the request failed due to rate limits.
    """
    log_level = logging.ERROR if rate_limit.message else logging.DEBUG

    logging.log(
        log_level,
        "GitHub rate limit headers: %s: %s, %s: %s, %s: %s",
        RATELIMIT_LIMIT_HEADER,
        rate_limit.limit,
        RATELIMIT_REMAINING_HEADER,
        rate_limit.remaining,
        RATELIMIT_RESET_HEADER,
        rate_limit.reset_time,
    )


class RateLimitingClient:
    """
    A rate limit respecting client.

    `request` is probably the only method you'll use,
    but you can preemptively check the rate limit with `is_rate_limited`.
    """

    def __init__(self, session: requests.Session):
        self._session = session
        self._last_rate_limit: Optional[RateLimit] = None

    def is_rate_limited(self, now: Optional[datetime] = None) -> bool:
        """
        Are we rate limited right now?
        """
        return self._rate_limited(now or datetime.now()) is not None

    def _rate_limited(self, now: datetime) -> Optional[RateLimit]:
        """
        Return `None` if not rate limited, or the RateLimit itself if currently limited.

        The RateLimit is returned instead of a bool so you don't have to check or cast
        `_last_rate_limit` to deal with `None` checking again.
        """
        if self._last_rate_limit is None:
            return None
        if self._last_rate_limit.remaining:
            return None
        if not self._last_rate_limit.is_limited_at(now):
            return None
        return self._last_rate_limit

    def request(self, request: requests.Request) -> requests.Response:
        """
        Send the request, taking into account rate limits.

        Will raise a GitHubRateLimitError if you try to send while
        we are still waiting out a current rate limit.

        The response's rate limit information will be logged.
        If the response is a rate limit error, a GitHubRateLimitError
        will be raised.
        """
        # TODO: do cached requests work when already rate limited?
        # might be an edge case we ignore.
        rate_limit = self._rate_limited(datetime.now())
        if rate_limit is not None:
            raise rate_limit.make_error(response=None)

        prepared = self._session.prepare_request(request)
        settings = self._session.merge_environment_settings(
            prepared.url, None, None, None, None
        )

        response = self._session.send(prepared, **settings)

        self._last_rate_limit = rate_limit = RateLimit.from_response(response)

        _log_ratelimit(rate_limit)

        if rate_limit.message is not None:
            # this means it was specifically a rate limit error response,
            # rather than the last request before running out.
            raise rate_limit.make_error(response)

        return response


__all__ = ["RateLimitingClient"]

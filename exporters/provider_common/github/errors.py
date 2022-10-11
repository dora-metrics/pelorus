"""
Errors from the GitHub API.
"""
from datetime import datetime
from typing import Optional

import requests
from attrs import frozen


@frozen
class GitHubError(Exception):
    """
    A generic error from the GitHub API.
    """

    response: Optional[requests.Response]
    message: Optional[str]

    def __attrs_post_init__(self):
        # python exceptions are weird.
        # The info they present in the traceback is baased on what's passed to __new__,
        # unless overridden in __init__.
        # We only care about the message, so we set that as the "args",
        # unless there is no message-- in which case we clear the info.
        if self.message:
            super().__init__(self.message)
        else:
            super().__init__()


class GitHubRateLimitError(GitHubError):
    """
    A rate limit was encountered.
    """

    reset_time: datetime

    def __attrs_post_init__(self):
        if self.message:
            Exception.__init__(self, self.message, self.reset_time)
        else:
            Exception.__init__(self, self.reset_time)


__all__ = ["GitHubError", "GitHubRateLimitError"]

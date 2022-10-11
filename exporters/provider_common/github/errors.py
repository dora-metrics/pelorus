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
    message: str = "Bad response from GitHub"


@frozen(kw_only=True)
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

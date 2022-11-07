"""
Utilities for presenting and handling paginated responses from GitHub
as per their pagination standard:
https://docs.github.com/en/rest/guides/traversing-with-pagination
"""
from __future__ import annotations

import itertools
from typing import Iterator, Optional

import requests
from attrs import frozen
from requests import HTTPError

from pelorus.utils import BadAttributePathError, get_nested

from .errors import GitHubError
from .rate_limit import RateLimitingClient


@frozen
class PageResponse:
    """
    A page of data from successful API response.
    """

    items: list
    response: requests.Response
    next_url: Optional[str]

    @classmethod
    def from_response(cls, response: requests.Response) -> PageResponse:
        """
        Validates that the response from github:
        - is a non-error response
        - is valid JSON
        - is a list

        Will return a GitHubError with any of the following set to the __cause__ if they occur:
        HTTPError if there's a bad response
        JSONDecodeError if there's a response with invalid JSON
        Or a plain GitHubError if the response was not a list.
        """
        try:
            response.raise_for_status()
            json = response.json()
            if not isinstance(json, list):
                raise GitHubError(response, f"Returned json was not a list: {json}")

            next_url: Optional[str] = get_nested(
                response.links, "next.url", default=None
            )

            return cls(json, response, next_url)
        except (
            HTTPError,
            requests.JSONDecodeError,
            ValueError,
            BadAttributePathError,
        ) as e:
            raise GitHubError(response) from e

    def __iter__(self) -> Iterator:
        return iter(self.items)


def paginate(
    client: RateLimitingClient,
    first_response: requests.Response,
    request_mod: Optional[dict] = None,
) -> Iterator[PageResponse]:
    """
    Request subsequent pages based on GitHub's pagination standard.
    This is useful if you need to inspect the response for each page,
    or handle each response as one chunk.

    `first_response` is the first response you get for the initial requested
    resource. If it does not have pagination headers, then you will only get
    one page back. This is done instead of making the request for you, so you
    can inspect the headers yourself before continuing.
    (e.g. perhaps it's a `304 Not Modified`, so you don't need more pages.)

    `request_mod` optionally lets you customize the `requests.Request`'s
    arguments.
    """
    response = first_response
    request_mod = request_mod or {}

    while True:
        page = PageResponse.from_response(response)

        yield page

        if page.next_url:
            request = requests.Request("GET", page.next_url, **request_mod)
            response = client.request(request)


def paginate_items(
    client: RateLimitingClient,
    first_response: requests.Response,
    request_mod: Optional[dict] = None,
) -> Iterator:
    """
    Iterate over all items in the resource pointed to by `first_response`,
    requesting the next page(s) as necessary.

    `first_response` is the first response you get for the initial requested
    resource. If it does not have pagination headers, then you will only get
    one page back. This is done instead of making the request for you, so you
    can inspect the headers yourself before continuing.
    (e.g. perhaps it's a `304 Not Modified`, so you don't need more pages.)

    `request_mod` optionally lets you customize the `requests.Request`'s
    arguments.
    """
    paginator = paginate(client, first_response, request_mod)
    return itertools.chain.from_iterable(paginator)


__all__ = ["PageResponse", "paginate", "paginate_items"]

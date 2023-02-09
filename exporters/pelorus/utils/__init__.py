#!/usr/bin/env python3
#
# Copyright Red Hat
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#


"""
Module utils contains helper utilities for common tasks in the codebase.
They are mainly to help with type information and to deal with data structures
in kubernetes that are not so idiomatic to deal with.
"""
import logging
import os
from typing import ClassVar, Generator, Optional, cast, overload

import requests
import requests.auth
import urllib3
from kubernetes import client, config
from kubernetes.dynamic import Resource, ResourceInstance
from openshift.dynamic import DynamicClient

from pelorus.certificates import set_up_requests_certs
from pelorus.utils.nested import (
    BadAttributePathError,
    collect_bad_attribute_path_error,
    format_path,
    get_nested,
    split_path,
)

DEFAULT_VAR_KEYWORD = "default"


class SpecializeDebugFormatter(logging.Formatter):
    """
    Uses a different format for DEBUG messages that has more information.
    """

    DEBUG_FORMAT = "%(asctime)-15s %(levelname)-8s %(pathname)s:%(lineno)d %(funcName)s() %(message)s"

    def format(self, record):
        prior_format = self._style._fmt

        try:
            if record.levelno == logging.DEBUG:
                self._style._fmt = self.DEBUG_FORMAT

            return logging.Formatter.format(self, record)
        finally:
            self._style._fmt = prior_format


@overload
def get_env_var(var_name: str, default_value: str) -> str:
    ...


@overload
def get_env_var(var_name: str) -> Optional[str]:
    ...


def get_env_var(var_name: str, default_value: Optional[str] = None) -> Optional[str]:
    """
    `get_env_var` modifies standard os.getenv behavior to allow using default python variable values
    when:
        1. PELORUS_DEFAULT_KEYWORD is set in SHELL env and the value from PELORUS_DEFAULT_KEYWORD
           is used for other SHELL env value, e.g.
           export PELORUS_DEFAULT_KEYWORD="custom_default"
           export LOG_LEVEL="custom_default"

           In which case LOG_LEVEL is set to DEFAULT_LOG_LEVEL

        2. DEFAULT_VAR_KEYWORD keyword is present as the SHELL env variable value, e.g.
           unset PELORUS_DEFAULT_KEYWORD
           export LOG_LEVEL="default"

           In which case LOG_LEVEL is set to DEFAULT_LOG_LEVEL

    This is required for the config map to define fallback vars in a consistent way.
    """

    # decision table
    # substitute PELORUS_DEFAULT_KEYWORD with whatever it is configured to be
    # | env var value           | default_value | result        |
    # | ----------------------- | ------------- | ------------- |
    # | unset                   | None          | None          |
    # | unset                   | any str       | default_value |
    # | ""                      | None          | ""            |
    # | ""                      | any str       | ""            |
    # | PELORUS_DEFAULT_KEYWORD | None          | ValueError    |
    # | PELORUS_DEFAULT_KEYWORD | any str       | default_value |
    # | any other str           | None          | env var value |
    # | any other str           | any str       | env var value |
    default_keyword = os.getenv("PELORUS_DEFAULT_KEYWORD") or DEFAULT_VAR_KEYWORD

    env_var = os.getenv(var_name, default_value)
    if env_var == default_keyword:
        if default_value is None:
            raise ValueError(f"default value not present for SHELL env var: {var_name}")
        return default_value

    return env_var


def get_k8s_client():
    """
    `get_k8s_client` provides interface to get dynamic Kubernetes client to access cluster
    information by the exporters.
    """
    k8s_client = None
    try:
        k8sconfig = config.new_client_from_config()
        k8s_client = DynamicClient(k8sconfig)
    except config.config_exception.ConfigException:
        # Try load config from cluster
        config.load_incluster_config()
        k8sconfig = client.Configuration().get_default_copy()
        client.Configuration.set_default(k8sconfig)
        k8s_client = DynamicClient(client.ApiClient(k8sconfig))

    return k8s_client


class TokenAuth(requests.auth.AuthBase):
    """
    Add token authentication to a requests Request or Session.
    """

    def __init__(self, token: str, is_pagerduty: bool = False):
        self.auth_str = f"Token token={token}" if is_pagerduty else f"token {token}"

    def __call__(self, r: requests.PreparedRequest):
        r.headers["Authorization"] = self.auth_str
        return r


@overload
def set_up_requests_session(
    session: requests.Session,
    verify: Optional[bool],
    *,
    auth: Optional[requests.auth.AuthBase] = None,
):
    ...


@overload
def set_up_requests_session(
    session: requests.Session,
    verify: Optional[bool],
    *,
    username: str,
    token: str,
):
    ...


def set_up_requests_session(
    session: requests.Session, verify: Optional[bool], **kwargs
):
    "Configures a requests session for proper TLS handling and auth."
    session.verify = set_up_requests_certs(verify)
    if "auth" in kwargs:
        auth: Optional[requests.auth.AuthBase] = kwargs["auth"]
        session.auth = auth
    elif "username" in kwargs and "token" in kwargs:
        username = kwargs["username"]
        token = kwargs["token"]
        if username and token:
            session.auth = (username, token)


def join_url_path_components(*components: str) -> str:
    return "/".join(c.strip("/") for c in components)


def paginate_resource(
    resource: Resource,
    query: dict[str, str],
    # completely arbitrary. Could experiment.
    limit: int = 50,
) -> Generator[ResourceInstance, None, None]:
    """
    Paginate requests for openshift resources.
    """
    client = cast(DynamicClient, resource.client)

    list_ = client.get(resource, **query, limit=limit)

    yield from list_.items

    continue_token = list_.metadata.get("continue")

    while continue_token:
        list_ = client.get(resource, **query, limit=limit, _continue=continue_token)
        yield from list_.items


class Url(urllib3.util.Url):
    """
    A URL.

    A really tiny abstraction over a urllib3.util.Url to solve one small issue with its path handling:
    if the path does not have a leading slash, it will not add one when converting to a string.

    We use urllib3's url instead of the stdlib's `urllib.parse` because `urllib.parse` assumes
    that a string without a scheme means a _path_, instead of a netloc/host.
    That is almost never the behavior we want.
    """

    VALID_SCHEMES: ClassVar[set[str]] = {"https", "http"}

    scheme: Optional[str]
    auth: Optional[str]
    host: Optional[str]
    port: Optional[str]
    path: Optional[str]
    query: Optional[str]
    fragment: Optional[str]

    @classmethod
    def parse(cls, url: str):
        parsed = urllib3.util.parse_url(url)

        if parsed.scheme is None:
            parsed = parsed._replace(scheme="https")
        elif parsed.scheme not in cls.VALID_SCHEMES:
            # edge case: a non-qualified hostname with a port specified
            # will parse as a scheme.
            # If that's the case, redo it with a scheme attached.
            parsed = urllib3.util.parse_url("https://" + url)

        return cls(*parsed)

    @property
    def url(self) -> str:
        if self.path and not self.path.startswith("/"):
            self = self._replace(path=f"/{self.path}")
        return super(Url, self).url

    def __bool__(self):
        return any(self)

    def __str__(self):
        return self.url

    def __contains__(self, needle: str):
        return needle in self.url


__all__ = [
    "SpecializeDebugFormatter",
    "DEFAULT_VAR_KEYWORD",
    "get_env_var",
    "get_k8s_client",
    "TokenAuth",
    "set_up_requests_session",
    "join_url_path_components",
    "paginate_resource",
    "Url",
    "BadAttributePathError",
    "collect_bad_attribute_path_error",
    "format_path",
    "get_nested",
    "split_path",
]

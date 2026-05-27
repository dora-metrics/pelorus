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


"""Shared utilities: env var handling, Kubernetes client setup, HTTP/TLS helpers, and URL parsing."""
import json as _json
import logging
import os
from typing import ClassVar, Generator, Optional, cast, overload

import requests
import requests.auth
import urllib3
from kubernetes import client, config
from kubernetes.dynamic import DynamicClient, Resource, ResourceInstance

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
    DEBUG_FORMAT = "%(asctime)-15s %(levelname)-8s [%(name)s] %(pathname)s:%(lineno)d %(funcName)s() %(message)s"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._debug_formatter = logging.Formatter(self.DEBUG_FORMAT)

    def format(self, record):
        if record.levelno == logging.DEBUG:
            return self._debug_formatter.format(record)
        return super().format(record)


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter for production log aggregation systems."""

    _STANDARD_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)

    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "pid": record.process,
        }
        if record.threadName != "MainThread":
            log_entry["thread"] = record.threadName
        if record.levelno == logging.DEBUG:
            log_entry["pathname"] = record.pathname
            log_entry["lineno"] = record.lineno
            log_entry["funcName"] = record.funcName
        if record.exc_info and record.exc_info[1]:
            log_entry["exception_type"] = type(record.exc_info[1]).__name__
            log_entry["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_entry["stack_info"] = self.formatStack(record.stack_info)
        for key, value in record.__dict__.items():
            if key not in self._STANDARD_RECORD_ATTRS:
                log_entry[key] = value
        return _json.dumps(log_entry, default=str)


@overload
def get_env_var(var_name: str, default_value: str) -> str:
    ...


@overload
def get_env_var(var_name: str) -> Optional[str]:
    ...


def get_env_var(var_name: str, default_value: Optional[str] = None) -> Optional[str]:
    """
    Like os.getenv, but if the env var equals the default keyword
    (PELORUS_DEFAULT_KEYWORD or "default"), return default_value instead.
    Raises ValueError if the keyword is matched but no default_value is provided.
    """
    raw_keyword = os.getenv("PELORUS_DEFAULT_KEYWORD")
    default_keyword = raw_keyword if raw_keyword is not None else DEFAULT_VAR_KEYWORD

    env_var = os.getenv(var_name, default_value)
    if env_var == default_keyword:
        if default_value is None:
            raise ValueError(f"default value not present for env var: {var_name}")
        return default_value

    return env_var


def get_k8s_client():
    try:
        k8sconfig = config.new_client_from_config()
        k8s_client = DynamicClient(k8sconfig)
        logging.info("Kubernetes client initialized from kubeconfig")
        return k8s_client
    except config.config_exception.ConfigException:
        logging.debug("Kubeconfig not available, trying in-cluster config")
    except OSError:
        logging.warning("Kubeconfig found but client creation failed, trying in-cluster config", exc_info=True)
    try:
        config.load_incluster_config()
        k8sconfig = client.Configuration().get_default_copy()
        client.Configuration.set_default(k8sconfig)
        k8s_client = DynamicClient(client.ApiClient(k8sconfig))
        logging.info("Kubernetes client initialized from in-cluster config")
        return k8s_client
    except config.config_exception.ConfigException as exc:
        raise RuntimeError(
            "Could not configure Kubernetes client: "
            "neither kubeconfig nor in-cluster config available"
        ) from exc


class TokenAuth(requests.auth.AuthBase):
    def __init__(self, token: str, is_pagerduty: bool = False):
        self._auth_str = f"Token token={token}" if is_pagerduty else f"token {token}"

    def __repr__(self):
        return "TokenAuth(***)"

    def __call__(self, r: requests.PreparedRequest):
        r.headers["Authorization"] = self._auth_str
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
    """Configures a requests session for proper TLS handling and auth."""
    session.trust_env = False
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
    limit: int = 50,
) -> Generator[ResourceInstance, None, None]:
    """Paginate through Kubernetes API list responses using continue tokens."""
    client = cast(DynamicClient, resource.client)

    list_ = client.get(resource, **query, limit=limit)

    yield from list_.items

    continue_token = list_.metadata.get("continue")

    while continue_token:
        list_ = client.get(resource, **query, limit=limit, _continue=continue_token)
        yield from list_.items
        continue_token = list_.metadata.get("continue")


class Url(urllib3.util.Url):
    """
    URL wrapper over urllib3.util.Url with scheme defaulting, path normalization,
    and string containment checks.

    Uses urllib3 instead of ``urllib.parse`` because the stdlib assumes
    a string without a scheme is a path, not a host — rarely what we want.
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
        obj = self
        if self.path and not self.path.startswith("/"):
            obj = self._replace(path=f"/{self.path}")
        return super(Url, obj).url

    def __bool__(self):
        return any(self)

    def __str__(self):
        return self.url

    def __contains__(self, needle: str):
        return needle in self.url


__all__ = [
    "SpecializeDebugFormatter",
    "JsonFormatter",
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

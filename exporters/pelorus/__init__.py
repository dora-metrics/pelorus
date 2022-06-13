import logging
import os
import pathlib
from abc import ABC
from datetime import datetime, timezone
from typing import Optional, Sequence

from . import utils

DEFAULT_APP_LABEL = "app.kubernetes.io/name"
DEFAULT_PROD_LABEL = ""
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)-15s %(levelname)-8s %(message)s"
DEFAULT_LOG_DATE_FORMAT = "%m-%d-%Y %H:%M:%S"
DEFAULT_GIT = "github"
DEFAULT_GIT_API = ""
DEFAULT_TLS_VERIFY = "True"
DEFAULT_TRACKER = "jira"
DEFAULT_TRACKER_APP_LABEL = "unknown"
DEFAULT_TRACKER_APP_FIELD = "u_application"


def _print_version():
    """
    Print the version of the currently running collector.
    Gets the collector name from inspecting `__main__`.
    Gets version information from environment variables set by an S2I build.
    """
    import __main__

    # name of dir above app.py
    exporter_name = pathlib.PurePath(__main__.__file__).parent.name

    repo, ref, commit = (
        utils.get_env_var(f"OPENSHIFT_BUILD_{var.upper()}")
        for var in "source reference commit".split()
    )
    if repo and ref and commit:
        print(
            f"Running {exporter_name} exporter from {repo}, ref {ref} (commit {commit})"
        )
    else:
        image_tag = utils.get_env_var("PELORUS_IMAGE_TAG")
        if image_tag:
            print(f"Running {exporter_name} exporter from the image: {image_tag}.")
        else:
            print(f"Running {exporter_name} exporter. No version information found.")


# region: logging setup
def _setup_logging():
    _print_version()
    loglevel = utils.get_env_var("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    numeric_level = getattr(logging, loglevel, None)
    if not isinstance(numeric_level, int):
        raise ValueError("Invalid log level: %s", loglevel)
    root_logger = logging.getLogger()
    formatter = utils.SpecializeDebugFormatter(
        fmt=DEFAULT_LOG_FORMAT, datefmt=DEFAULT_LOG_DATE_FORMAT
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)
    print(f"Initializing Logger with LogLevel: {loglevel}")


_setup_logging()


# endregion

# A NamespaceSpec lists namespaces to restrict the search to.
# Use None or an empty list to include all namespaces.
NamespaceSpec = Optional[Sequence[str]]


def convert_date_time_to_timestamp(date_time, format_string="%Y-%m-%dT%H:%M:%SZ"):
    timestamp = None
    try:
        if isinstance(date_time, datetime):
            timestamp = date_time
        else:
            timestamp = datetime.strptime(date_time, format_string)
    except ValueError:
        raise
    return timestamp.replace(tzinfo=timezone.utc).timestamp()


def convert_timestamp_to_date_time_str(timestamp, format_string="%Y-%m-%dT%H:%M:%SZ"):
    date_time_str = None
    try:
        date_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        date_time_str = date_time.strftime(format_string)
    except ValueError:
        raise
    return date_time_str


def get_app_label():
    return utils.get_env_var("APP_LABEL", DEFAULT_APP_LABEL)


def get_prod_label():
    return utils.get_env_var("PROD_LABEL", DEFAULT_PROD_LABEL)


def missing_configs(vars):
    missing_configs = False
    for var in vars:
        if utils.get_env_var(var) is None:
            logging.error("Missing required environment variable '%s'." % var)
            missing_configs = True

    return missing_configs


def upgrade_legacy_vars():
    username = utils.get_env_var("GITHUB_USER")
    token = utils.get_env_var("GITHUB_TOKEN")
    api = utils.get_env_var("GITHUB_API", DEFAULT_GIT_API)
    if username and not utils.get_env_var("GIT_USER"):
        os.environ["GIT_USER"] = username
    if token and not utils.get_env_var("GIT_TOKEN"):
        os.environ["GIT_TOKEN"] = token
    if api and not utils.get_env_var("GIT_API"):
        os.environ["GIT_API"] = api


def url_joiner(url, path, trailing=None):
    """Join to sections for a URL and add proper forward slashes"""
    url_link = "/".join(s.strip("/") for s in [url, path])
    if trailing:
        url_link += "/"
    return url_link


class AbstractPelorusExporter(ABC):
    """
    Base class for PelorusExporter
    """

    def __init_():
        pass

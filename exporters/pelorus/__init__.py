import logging
import os
import pathlib
from abc import ABC
from typing import Optional, Sequence

from prometheus_client.registry import Collector

from . import utils

DEFAULT_APP_LABEL = "app.kubernetes.io/name"
DEFAULT_PROD_LABEL = ""
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)-15s %(levelname)-8s %(message)s"
DEFAULT_LOG_DATE_FORMAT = "%m-%d-%Y %H:%M:%S"
DEFAULT_GIT = "github"
DEFAULT_GIT_API = ""
DEFAULT_TLS_VERIFY = True
DEFAULT_TRACKER = "jira"
DEFAULT_TRACKER_APP_LABEL = "unknown"
DEFAULT_TRACKER_APP_FIELD = "u_application"
DEFAULT_GITHUB_ISSUE_LABEL = "bug"


def _print_version():
    """
    Print the version of the currently running collector.
    Gets the collector name from inspecting `__main__`.
    Gets version information from environment variables set by an S2I build.
    """
    import __main__

    file = getattr(__main__, "__file__", None)
    if file:
        # name of dir above app.py
        exporter_name = pathlib.PurePath(file).parent.name
    else:
        exporter_name = "INTERPRETER"

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
def setup_logging():
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


# endregion

# A NamespaceSpec lists namespaces to restrict the search to.
# Use None or an empty list to include all namespaces.
NamespaceSpec = Optional[Sequence[str]]


def get_app_label():
    return utils.get_env_var("APP_LABEL", DEFAULT_APP_LABEL)


def get_prod_label():
    return utils.get_env_var("PROD_LABEL", DEFAULT_PROD_LABEL)


def get_github_issue_label():
    return utils.get_env_var("GITHUB_ISSUE_LABEL", DEFAULT_GITHUB_ISSUE_LABEL)


def missing_configs(vars):
    missing_configs = False
    for var in vars:
        if utils.get_env_var(var) is None:
            logging.error("Missing required environment variable '%s'." % var)
            missing_configs = True

    return missing_configs


def upgrade_legacy_vars():
    github_token = utils.get_env_var("GITHUB_TOKEN")
    git_token = utils.get_env_var("GIT_TOKEN")
    api = utils.get_env_var("GITHUB_API", DEFAULT_GIT_API)

    api_user = utils.get_env_var("API_USER")
    github_user = utils.get_env_var("GITHUB_USER")
    git_username = utils.get_env_var("GIT_USER")

    assigned_user = api_user or git_username or github_user

    if assigned_user:
        os.environ["API_USER"] = assigned_user

    if not utils.get_env_var("TOKEN"):
        if git_token or github_token:
            os.environ["TOKEN"] = git_token or github_token
    if api and not utils.get_env_var("GIT_API"):
        os.environ["GIT_API"] = api


def url_joiner(base: str, *parts: str):
    """
    Joins each part together (including the base url) with a slash, stripping any leading or trailing slashes.
    Used for "normalizing" URLs to handle most use cases.
    """
    return base.strip("/") + "/" + "/".join(s.strip("/") for s in parts)


class AbstractPelorusExporter(Collector, ABC):
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        # make sure __hash__ is something prometheus' registry can handle properly.
        cls.__hash__ = lambda self: id(self)  # type: ignore

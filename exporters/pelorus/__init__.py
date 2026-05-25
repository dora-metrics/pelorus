import logging
import os
import pathlib
from abc import ABC
from attrs import define
from prometheus_client.registry import Collector

from . import utils
from .timeutil import METRIC_TIMESTAMP_THRESHOLD_MINUTES

_port_raw = os.environ.get("PELORUS_PORT", "8080")
try:
    EXPORTER_PORT = int(_port_raw)
except ValueError as exc:
    raise ValueError(f"PELORUS_PORT must be an integer, got: {_port_raw!r}") from exc
if not (1 <= EXPORTER_PORT <= 65535):
    raise ValueError(f"PELORUS_PORT must be between 1 and 65535, got: {EXPORTER_PORT}")

DEFAULT_APP_LABEL = "app.kubernetes.io/name"
DEFAULT_PROD_LABEL = ""
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)-15s %(levelname)-8s [%(name)s] %(message)s"
DEFAULT_LOG_DATE_FORMAT = "%m-%d-%Y %H:%M:%S"
DEFAULT_GIT = "github"
DEFAULT_TLS_VERIFY = True
DEFAULT_TRACKER = "jira"
DEFAULT_TRACKER_APP_LABEL = "unknown"
DEFAULT_TRACKER_APP_FIELD = "u_application"


def _print_version():
    import __main__

    file = getattr(__main__, "__file__", None)
    if file:
        # name of dir above app.py
        exporter_name = pathlib.PurePath(file).parent.name
    else:
        exporter_name = "INTERPRETER"

    repo, ref = (
        utils.get_env_var(f"OPENSHIFT_BUILD_{var}") for var in ["SOURCE", "REFERENCE"]
    )
    if repo and ref:
        logging.info("Running %s exporter from repo %s ref %s", exporter_name, repo, ref)
    else:
        image_tag = utils.get_env_var("PELORUS_IMAGE_TAG")
        if image_tag:
            logging.info("Running %s exporter from the image: %s.", exporter_name, image_tag)
        else:
            logging.info("Running %s exporter. No version information found.", exporter_name)


_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def setup_logging(prod: bool = True):
    loglevel = utils.get_env_var("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    if loglevel not in _VALID_LOG_LEVELS:
        raise ValueError(f"Invalid log level: {loglevel}")
    numeric_level = getattr(logging, loglevel)
    root_logger = logging.getLogger()
    formatter = utils.SpecializeDebugFormatter(
        fmt=DEFAULT_LOG_FORMAT, datefmt=DEFAULT_LOG_DATE_FORMAT
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    # Clear existing handlers in prod to avoid duplicates from background threads
    if prod and root_logger.hasHandlers():
        root_logger.handlers = []
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)
    logging.info("Initializing Logger with LogLevel: %s", loglevel)
    logging.info("PELORUS_TIMESTAMP_THRESHOLD_MINUTES=%d", METRIC_TIMESTAMP_THRESHOLD_MINUTES)
    _print_version()



def url_joiner(base: str, *parts: str) -> str:
    """
    Joins each part together (including the base url) with a slash, stripping any leading or trailing slashes.
    Used for "normalizing" URLs to handle most use cases.
    """
    return base.strip("/") + "/" + "/".join(s.strip("/") for s in parts)


@define(kw_only=True)
class AbstractPelorusExporter(Collector, ABC):
    app_label: str = DEFAULT_APP_LABEL

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        # make sure __hash__ is something prometheus' registry can handle properly.
        cls.__hash__ = lambda self: id(self)  # type: ignore

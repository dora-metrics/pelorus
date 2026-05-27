import logging
import os
import pathlib
from abc import ABC
from attrs import define
from prometheus_client import Gauge, Info
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
DEFAULT_LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
DEFAULT_GIT = "github"
DEFAULT_TLS_VERIFY = True
DEFAULT_TRACKER = "jira"
DEFAULT_TRACKER_APP_LABEL = "unknown"
DEFAULT_TRACKER_APP_FIELD = "u_application"


_exporter_info = Info("pelorus_exporter", "Pelorus exporter build and runtime info")

_startup_success = Gauge(
    "pelorus_exporter_startup_success",
    "Whether the exporter started up and configured successfully (1=success, 0=failure)",
)


def mark_startup(success: bool):
    _startup_success.set(success)


def _print_version():
    import __main__

    file = getattr(__main__, "__file__", None)
    if file:
        exporter_name = pathlib.PurePath(file).parent.name
    else:
        exporter_name = "INTERPRETER"

    repo = utils.get_env_var("OPENSHIFT_BUILD_SOURCE")
    ref = utils.get_env_var("OPENSHIFT_BUILD_REFERENCE")
    info_labels = {"exporter": exporter_name}
    if repo and ref:
        logging.info("Running %s exporter from repo %s ref %s", exporter_name, repo, ref)
        info_labels["repo"] = repo
        info_labels["ref"] = ref
    else:
        image_tag = utils.get_env_var("PELORUS_IMAGE_TAG")
        if image_tag:
            logging.info("Running %s exporter from the image: %s.", exporter_name, image_tag)
            info_labels["image_tag"] = image_tag
        else:
            logging.info("Running %s exporter. No version information found.", exporter_name)
    _exporter_info.info(info_labels)


_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
_VALID_LOG_FORMATS = frozenset({"text", "json"})


def setup_logging(prod: bool = True):
    loglevel = utils.get_env_var("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    if loglevel not in _VALID_LOG_LEVELS:
        raise ValueError(f"Invalid log level: {loglevel}")
    numeric_level = getattr(logging, loglevel)
    root_logger = logging.getLogger()
    log_format = (utils.get_env_var("LOG_FORMAT", "text") or "text").lower()
    if log_format not in _VALID_LOG_FORMATS:
        raise ValueError(
            f"Invalid LOG_FORMAT: {log_format!r}, must be one of {sorted(_VALID_LOG_FORMATS)}"
        )
    if log_format == "json":
        formatter = utils.JsonFormatter(datefmt=DEFAULT_LOG_DATE_FORMAT)
    else:
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
    """Join URL path components with '/', stripping leading/trailing slashes from each part."""
    return utils.join_url_path_components(base, *parts)


@define(kw_only=True)
class AbstractPelorusExporter(Collector, ABC):
    app_label: str = DEFAULT_APP_LABEL

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        # make sure __hash__ is something prometheus' registry can handle properly.
        cls.__hash__ = lambda self: id(self)  # type: ignore

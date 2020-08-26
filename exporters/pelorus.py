from abc import ABC
import logging
import os
import sys
from datetime import datetime, timezone
from kubernetes import config

DEFAULT_APP_LABEL = 'app.kubernetes.io/name'
DEFAULT_PROD_LABEL = ''
DEFAULT_LOG_LEVEL = 'INFO'
DEFAULT_LOG_FORMAT = '%(asctime)-15s %(levelname)-8s %(message)s'
DEFAULT_LOG_DATE_FORMAT = '%m-%d-%Y %H:%M:%S'
DEFAULT_GIT = "github"

loglevel = os.getenv('LOG_LEVEL', DEFAULT_LOG_LEVEL)
numeric_level = getattr(logging, loglevel.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)
logging.basicConfig(format=DEFAULT_LOG_FORMAT, datefmt=DEFAULT_LOG_DATE_FORMAT, level=numeric_level)
print("Initializing Logger wit LogLevel: %s" % loglevel.upper())


def load_kube_config():
    if "OPENSHIFT_BUILD_NAME" in os.environ:
        config.load_incluster_config()
        file_namespace = open(
            "/run/secrets/kubernetes.io/serviceaccount/namespace", "r"
        )
        if file_namespace.mode == "r":
            namespace = file_namespace.read()
            print("namespace: %s\n" % (namespace))
    else:
        config.load_kube_config()


def convert_date_time_to_timestamp(date_time, format_string='%Y-%m-%dT%H:%M:%SZ'):
    timestamp = None
    try:
        timestamp = datetime.strptime(date_time, format_string)
    except ValueError:
        raise
    return timestamp.replace(tzinfo=timezone.utc).timestamp()


def get_app_label():
    return os.getenv('APP_LABEL', DEFAULT_APP_LABEL)


def get_prod_label():
    return os.getenv('PROD_LABEL', DEFAULT_PROD_LABEL)


def check_required_config(vars):
    missing_configs = False
    for var in vars:
        if var not in os.environ:
            logging.error("Missing required environment variable '%s'." % var)
            missing_configs = True

    if missing_configs:
        logging.error("This program will exit.")
        sys.exit(1)


def check_legacy_vars():
    username = os.environ.get('GITHUB_USER')
    token = os.environ.get('GITHUB_TOKEN')
    api = os.environ.get('GITHUB_API')
    if username is not None:
        os.environ['GIT_USER'] = username
    if token is not None:
        os.environ['GIT_TOKEN'] = token
    if api is not None:
        os.environ['GIT_API'] = api


class AbstractPelorusExporter(ABC):
    """
    Base class for PelorusExporter
    """
    def __init_():
        pass

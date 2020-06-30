import logging
import os
import sys
from datetime import datetime, timezone
from kubernetes import config

DEFAULT_APP_LABEL = 'app.kubernetes.io/name'
DEFAULT_PROD_LABEL = ''
DEFAULT_LOG_LEVEL = 'INFO'

loglevel = os.getenv('LOG_LEVEL', DEFAULT_LOG_LEVEL)
numeric_level = getattr(logging, loglevel.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)
logging.basicConfig(level=numeric_level)
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


def convert_date_time_to_timestamp(date_time):
    # Confirm we have a proper float value
    str(date_time)
    timestamp = datetime.strptime(date_time, '%Y-%m-%dT%H:%M:%SZ')
    unixformattime = timestamp.replace(tzinfo=timezone.utc).timestamp()
    return unixformattime


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

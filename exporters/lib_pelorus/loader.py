import os
from datetime import datetime, timezone
from kubernetes import config

def load_kube_config():
    if "OPENSHIFT_BUILD_NAME" in os.environ:
        config.load_incluster_config()
        file_namespace = open(
            "/run/secrets/kubernetes.io/serviceaccount/namespace", "r"
        )
        if file_namespace.mode == "r":
            namespace = file_namespace.read()
            print("namespace: %s\n" %(namespace))
    else:
        config.load_kube_config()

def convert_date_time_to_timestamp(date_time):
    timestamp = datetime.strptime(date_time, '%Y-%m-%dT%H:%M:%SZ')
    unixformattime = timestamp.replace(tzinfo=timezone.utc).timestamp()
    return unixformattime       

def get_app_label():
    return os.getenv('APP_LABEL', 'application')

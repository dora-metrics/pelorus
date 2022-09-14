import time

from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

import pelorus
from extra.releasetime import collector_github

if __name__ == "__main__":
    pelorus.setup_logging()
    collector = collector_github.make_collector()

    REGISTRY.register(collector)
    start_http_server(8080)
    while True:
        time.sleep(1)

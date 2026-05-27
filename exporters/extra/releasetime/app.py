import time

from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

import pelorus
from extra.releasetime import collector_github

if __name__ == "__main__":
    import logging

    pelorus.setup_logging()

    try:
        collector = collector_github.make_collector()
        REGISTRY.register(collector)
        pelorus.mark_startup(True)
    except Exception as e:
        pelorus.mark_startup(False)
        logging.error(
            "Failed to configure releasetime exporter: %s. "
            "Set PROJECTS and required provider settings (e.g. TOKEN, GIT_API). "
            "Starting metrics server anyway - configure and restart to collect release data.",
            e,
            exc_info=True,
        )

    start_http_server(pelorus.EXPORTER_PORT)
    logging.info("Releasetime exporter ready, serving metrics on :%d", pelorus.EXPORTER_PORT)
    while True:
        time.sleep(60)

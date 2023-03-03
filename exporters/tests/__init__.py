from prometheus_client.core import REGISTRY

from pelorus import AbstractPelorusExporter


def run_prometheus_register(collector: AbstractPelorusExporter) -> None:
    try:
        REGISTRY.register(collector)
    finally:
        REGISTRY.unregister(collector)

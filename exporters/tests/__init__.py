import logging
import os
from collections.abc import Callable
from unittest.mock import Mock, patch

from prometheus_client.core import REGISTRY, Metric

from pelorus import AbstractPelorusExporter, utils


def get_number_of_logs(
    log_record_tuples: list[tuple[str, int, str]], level: int
) -> int:
    return len([record for record in log_record_tuples if record[1] == level])


def get_number_of_error_logs(log_record_tuples: list[tuple[str, int, str]]) -> int:
    return get_number_of_logs(log_record_tuples, level=logging.ERROR)


def get_number_of_info_logs(log_record_tuples: list[tuple[str, int, str]]) -> int:
    return get_number_of_logs(log_record_tuples, level=logging.INFO)


def run_prometheus_register(collector: AbstractPelorusExporter) -> None:
    try:
        REGISTRY.register(collector)
        metrics = list(collector.collect())
        assert len(metrics) > 0
        for m in metrics:
            assert isinstance(m, Metric), f"Expected Metric instance, got {type(m).__name__}"
    finally:
        REGISTRY.unregister(collector)


class MockExporter:
    def __init__(
        self, set_up: Callable[[], AbstractPelorusExporter], mock_kube_client=None
    ) -> None:
        self.set_up = set_up
        self.mock_kube_client = mock_kube_client if mock_kube_client is not None else Mock()

    def run_app(self, arguments: dict[str, str]) -> AbstractPelorusExporter:
        """Run set up of exporter app with desired environment variables."""
        saved: dict[str, str | None] = {}
        try:
            collector = None
            for key, value in arguments.items():
                saved[key] = os.environ.get(key)
                os.environ[key] = value
            with patch.object(utils, "get_k8s_client") as mock_kube_client:
                mock_kube_client.return_value.resources.get.side_effect = (
                    self.mock_kube_client
                )
                collector = self.set_up(prod=False)
            return collector
        finally:
            for key, original in saved.items():
                if original is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original
            if collector:
                REGISTRY.unregister(collector)

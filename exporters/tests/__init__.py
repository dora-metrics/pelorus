import logging
import os
from typing import Callable, Dict
from unittest.mock import Mock, patch

from prometheus_client.core import REGISTRY

from pelorus import AbstractPelorusExporter, utils


def run_prometheus_register(collector: AbstractPelorusExporter) -> None:
    try:
        REGISTRY.register(collector)
    finally:
        REGISTRY.unregister(collector)


class MockExporter:
    def __init__(
        self, set_up: Callable[[], AbstractPelorusExporter], mock_kube_client=Mock()
    ) -> None:
        self.set_up = set_up
        self.mock_kube_client = mock_kube_client

    def run_app(self, arguments: Dict[str, str]) -> AbstractPelorusExporter:
        """Run set up of exporter app with desired environment variables."""
        try:
            collector = None
            logging.getLogger().disabled = False
            for key, value in arguments.items():
                os.environ[key] = value
            with patch.object(utils, "get_k8s_client") as mock_kube_client:
                mock_kube_client.return_value.resources.get.side_effect = (
                    self.mock_kube_client
                )
                collector = self.set_up()
            return collector
        finally:
            for key in arguments:
                del os.environ[key]
            if collector:
                REGISTRY.unregister(collector)
            logging.getLogger().disabled = True

from http.server import HTTPServer
from pathlib import Path

import pytest
import requests


def test_custom_requests_certs(
    combined_certificates: Path,
    https_server: HTTPServer,
):
    session = requests.Session()
    session.verify = str(combined_certificates)

    session.get(f"https://127.0.0.1:{https_server.server_port}")


@pytest.mark.integration
def test_custom_certs_still_work_with_public_certs(combined_certificates: str):
    """
    Does our custom cert bundle still work with certifi root certs?
    """
    session = requests.Session()
    session.verify = combined_certificates

    session.get("https://example.net")

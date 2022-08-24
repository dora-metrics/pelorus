import os
import shutil
from contextlib import suppress
from threading import Thread

import pytest
from pytest import TempPathFactory

import tests.certs.utils.https as https
from pelorus.certificates import _combine_certificates
from tests.certs.utils.certs import CustomCerts, context_for_certs_dir, create_certs


@pytest.fixture
def custom_certs(tmp_path_factory: TempPathFactory) -> CustomCerts:
    """
    Get a bundle of custom certs.
    """
    return create_certs(tmp_path_factory.mktemp("custom-cert-workdir"))


@pytest.fixture
def combined_certificates(
    tmp_path_factory: TempPathFactory,
    custom_certs: CustomCerts,
):
    """
    Get the path to an alread-combined certificate bundle.
    """
    lookup_dir = tmp_path_factory.mktemp("custom_certs")

    cert_containing_dir = lookup_dir / "0"
    cert_containing_dir.mkdir()

    shutil.copy(custom_certs.bundle, cert_containing_dir)

    combined_bundle = _combine_certificates(lookup_dir)

    yield combined_bundle

    with suppress(IOError):
        os.remove(combined_bundle)


@pytest.fixture
def https_server(
    custom_certs: CustomCerts,
):
    """
    Get an https server serving on 127.0.0.1 using `custom_certs` for its TLS certificates.

    To find what port it is on, use `server.server_port`.
    """
    ctx = context_for_certs_dir(custom_certs)
    server = https.make_server(ctx)
    thread = Thread(
        target=server.serve_forever,
        name=f"https server with {custom_certs.bundle}",
    )
    thread.start()

    yield server

    server.shutdown()

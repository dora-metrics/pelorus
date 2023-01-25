"""
Certificate management.

`urllib3`/`requests`-based libraries use `certifi` for up-to-date,
platform-agnostic certificate handling.

There are also plenty of internal services that do not have certificates
signed by one of the `certifi`-trusted roots.

Giving custom certificates to `requests` means it _overrides_ checking certifi,
so we have to combine them ourselves.
"""
import atexit
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Union

import certifi

DEFAULT_CERT_DIR = Path("/etc/pelorus/custom_certs")


# TODO: validate and/or automate making sure the file is PEM versus DER?
# TODO: what if the certs are missing trailing newlines? Will they still work?
def _combine_certificates(dir_to_check: Path = DEFAULT_CERT_DIR) -> str:
    """
    Combines the certificates with the certificates from `certifi`.
    All certificates ending in `.pem` under each directory under `dir_to_check`
    is combined (e.g. `dir_to_check/*/*.pem`).
    Returns the path of the combined file.
    """
    target_fd, target_path = tempfile.mkstemp(suffix=".pem", prefix="custom-certs")

    with open(target_fd, "wb") as target:
        with open(certifi.where(), "rb") as source:
            shutil.copyfileobj(source, target)

        for source_path in dir_to_check.glob("*/*.pem"):
            logging.info("Combining custom certificate file %s", source_path)

            with source_path.open("rb") as source:
                target.write(f"# custom cert from {source_path}\n".encode())
                shutil.copyfileobj(source, target)

    logging.debug("Combined certificate bundle created at %s", target_path)
    return target_path


def _register_cleanup(path: str):
    """
    Clean up the tempfile at program exit.
    """
    atexit.register(os.remove, path)


def set_up_requests_certs(verify: Optional[bool] = None) -> Union[bool, str]:
    """
    Set up custom certificates based on the way requests is configured.

    In summary:

    If you already ask for a `tls_verify` variable, you'd do:
    `session.verify = set_up_requests_certs(tls_verify)`

    Otherwise, just do `session.verify = set_up_requests_certs()`.

    This should only be called once in the program's lifetime.
    We'll have to revisit this if there comes a use case for multiple Sessions.

    If `verify` is set to `True` or `None`, then this function will combine
    the certifi certs and the custom certs under `/etc/pelorus/custom_certs/*/*.pem`.

    It will combine them into a temporary file, the path of which is returned.
    It will also register that file for removal at program exit.

    If `verify` is `False`, `False` is returned for ease of use with the above example.
    """
    if verify is False:
        logging.warn(
            "Disabling TLS verification. Custom certificates are now supported, consider using them: "
            "https://pelorus.readthedocs.io/en/latest/GettingStarted/configuration/PelorusExporters/"
            "#custom-certificates"
        )
        return False

    file = _combine_certificates()
    _register_cleanup(file)

    return file


__all__ = ["set_up_requests_certs"]

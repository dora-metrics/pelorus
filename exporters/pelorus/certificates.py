"""
Certificate management.

`urllib3`/`requests`-based libraries use `certifi` for up-to-date,
platform-agnostic certificate handling.

There are also plenty of internal services that do not have certificates
signed by one of the `certifi`-trusted roots.

Giving custom certificates to `requests` means it _overrides_ checking certifi,
so we have to combine them ourselves.

Because we can't control third-party libraries that wrap `requests`,
we'll create our own combined file, and set the environment variable to point to it.
"""
import atexit
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterable, Union

import certifi
from attrs import field, frozen

from pelorus.config import load_and_log
from pelorus.config.converters import comma_separated


# TODO: validate and/or automate making sure the file is PEM versus DER?
def _combine_certificates(custom_cert_paths: Iterable[Union[str, Path]]) -> str:
    """
    Combines the certificates at the given paths with the certificates from `certifi`.
    Returns the path of the combined file.
    """
    target_fd, target_path = tempfile.mkstemp(suffix=".pem", prefix="custom-certs")

    with open(target_fd, "wb") as target:
        with open(certifi.where(), "rb") as source:
            shutil.copyfileobj(source, target)

        for source_path in custom_cert_paths:
            with open(source_path, "rb") as source:
                shutil.copyfileobj(source, target)

    logging.debug("Combined certificate bundle created at %s", target_path)
    return target_path


def _register_cleanup(path: str):
    """
    Clean up the tempfile at program exit.
    """
    atexit.register(os.remove, path)


@frozen
class RequestsCertificatesConfig:
    """
    Configuration for adding custom certificates
    for requests-based exporters.

    May expand to other uses in the future.
    """

    requests_custom_pem_cert_files: set[str] = field(
        factory=set, converter=comma_separated(set)
    )
    """
    A comma-separated list of paths to PEM-encoded certs.
    This verbose name is used to draw attention to the fact(s) that:
    - it is currently for requests-based exporters only.
    - it is looking for _file paths_, not the entire certificate itself.
    - the certs must be PEM encoded, not DER encoded.
    """


def set_up_requests_certs(
    verify: Union[bool, str, None] = None
) -> Union[bool, str, None]:
    """
    Set up custom certificates based on the way requests is configured.

    In summary:

    If you already ask for a `tls_verify` variable, you'd do:
    `session.verify = set_up_requests_certs(tls_verify)`

    Otherwise, just do `session.verify = set_up_requests_certs()`.

    This should only be called once in the program's lifetime.
    We'll have to revisit this if there comes a use case for multiple Sessions.

    If `verify` is set to a value that `requests` would use to check certificates
    (anything but False), then this function will combine the certifi certs
    and the custom certs given:

    - the certificates listed in the appropriate env vars (see RequestsCertificatesConfig)
    - the certificate file specified as an argument (if given a string)

    It will combine them into a temporary file, the path of which is returned.
    It will also register that file for removal at program exit.

    If given `True` or `None` and no certs are specified in the above env vars,
    that value is passed along, and no custom cert handling is performed.
    If given `False`, that is returned.
    """
    if verify is False:
        return False

    files = load_and_log(RequestsCertificatesConfig).requests_custom_pem_cert_files

    if isinstance(verify, str):
        files.add(verify)

    if files:
        verify = _combine_certificates(files)
        _register_cleanup(verify)

    return verify


__all__ = ["set_up_requests_certs"]

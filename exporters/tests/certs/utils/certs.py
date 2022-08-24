"""
Custom cert generation.
"""
import shutil
import ssl
import subprocess
from functools import partial
from pathlib import Path
from ssl import SSLContext
from typing import NamedTuple

CERT_X509_SAN_EXT_CONFIG = "subjectAltName=IP:127.0.0.1"


class CustomCerts(NamedTuple):
    """
    A cert chain bundle and a private key file.
    """

    bundle: Path
    keyfile: Path


def context_for_certs_dir(custom: CustomCerts) -> SSLContext:
    """
    Create an SSLContext based on the custom certs created with `create_certs`.
    """
    ctx = SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(custom.bundle, custom.keyfile)
    return ctx


def create_certs(working_dir: Path) -> CustomCerts:
    """
    NOTE: no security guarantees here-- this is just for testing.

    Create a CA certificate, leaf certificate,
    and an unencrypted private key for the leaf cert.
    """
    run = partial(subprocess.run, cwd=working_dir, check=True)

    # although we use absolute paths as args,
    # openssl produces some other files as side effects.
    priv_key_path = working_dir / "priv.key"
    ca_cert_path = working_dir / "ca.pem"
    csr_path = working_dir / "req.csr"
    csr_ext_path = working_dir / "req.csr.ext"
    leaf_cert_path = working_dir / "leaf.pem"
    bundle_path = working_dir / "bundle.pem"

    # create private key
    run(["openssl", "genpkey", "-algorithm", "rsa", "-out", priv_key_path])

    # create Certificate Authority cert
    run(
        [
            "openssl",
            "req",
            "-new",
            "-key",
            priv_key_path,
            "-x509",
            "-days",
            "1",
            "-subj",
            "/CN=Pelorus Test CA",
            "-out",
            ca_cert_path,
        ]
    )

    # create Certificate Signing Request
    run(
        [
            "openssl",
            "req",
            "-new",
            "-key",
            priv_key_path,
            "-subj",
            "/CN=Pelorus Localhost Test Leaf",
            "-out",
            csr_path,
        ]
    )

    # create config for Subject Alternative Names
    with csr_ext_path.open("w") as f:
        f.write(CERT_X509_SAN_EXT_CONFIG)

    # Create the leaf certificate signed by our CA
    run(
        [
            "openssl",
            "x509",
            "-req",
            "-in",
            csr_path,
            "-CA",
            ca_cert_path,
            "-CAkey",
            priv_key_path,
            "-CAcreateserial",
            "-out",
            leaf_cert_path,
            "-days",
            "1",
            "-sha256",
            "-extfile",
            csr_ext_path,
        ]
    )

    # combine into bundle
    with leaf_cert_path.open("rb") as leaf, ca_cert_path.open(
        "rb"
    ) as ca, bundle_path.open("wb") as bundle:
        shutil.copyfileobj(leaf, bundle)
        shutil.copyfileobj(ca, bundle)

    return CustomCerts(bundle_path, priv_key_path)

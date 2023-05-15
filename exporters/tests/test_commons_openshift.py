import pytest

from provider_common.openshift import _parse_container_image_uri


@pytest.mark.parametrize(
    "registry, image, sha",
    [
        (
            "quay.io/centos7/",
            "httpd-24-centos7",
            "@sha256:ac78ddd61b5d11f8d1f9e43bec63cce5f962d485f8cdd8e55f9ea8486878ba7b",
        ),
        (
            "image-registry.openshift-image-registry.svc:5000/openshift/",
            "httpd",
            "@sha256:95c922088ef9dec82db2ddd81b439c7f1df8d630af471f72c0e8d2606077ea7b",
        ),
    ],
)
def test_image_sha(registry: str, image: str, sha: str) -> None:
    assert _parse_container_image_uri(f"{registry}{image}{sha}") == (
        registry,
        image,
        sha.replace("@", ""),
    )


@pytest.mark.parametrize(
    "registry, image, sha",
    [
        (
            None,
            "httpd-24-centos7",
            "@sha256:ac78ddd61b5d11f8d1f9e43bec63cce5f962d485f8cdd8e55f9ea8486878ba7b",
        ),
        (
            None,
            None,
            "@sha256:ac78ddd61b5d11f8d1f9e43bec63cce5f962d485f8cdd8e55f9ea8486878ba7b",
        ),
        (None, "httpd-24-centos7", None),
        ("quay.io/centos7/", "httpd-24-centos7", ":latest"),
    ],
)
def test_image_sha_bad_uri(registry: str, image: str, sha: str) -> None:
    uri = [part for part in [registry, image, sha] if part is not None]
    uri_string = "".join(uri)
    ret_registry, ret_image, ret_sha = _parse_container_image_uri(uri_string)
    assert ret_registry is None
    assert ret_image is None
    assert ret_sha is None

import os

import pelorus


def test_get_app_label():
    os.environ["APP_LABEL"] = "changed"
    assert pelorus.get_app_label() == "changed"
    os.unsetenv("APP_LABEL")


def test_get_prod_label():
    assert pelorus.get_prod_label() == pelorus.DEFAULT_PROD_LABEL
    os.environ["PROD_LABEL"] = "changed"
    assert pelorus.get_prod_label() == "changed"
    os.unsetenv("PROD_LABEL")

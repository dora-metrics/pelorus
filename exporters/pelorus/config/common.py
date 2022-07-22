from typing import Any

Metadata = dict[str, Any]
"""
A bit of metadata is a dict.
In pelorus.config, we combine them with the union operator:
metadata1() | metadata2()
"""

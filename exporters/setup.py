#!/usr/bin/env python3

import setuptools

setuptools.setup(
    packages=setuptools.find_packages(where="."),
    setup_requires=["pbr>=2.0.0"],
    python_requires=">=3.9",
    pbr=True,
)

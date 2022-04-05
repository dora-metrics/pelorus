# Scripts

Various scripts for development reside here.

## setup-dev-env

Sets up a python3.9 virtual environment, installs dependencies, and sets up the pre-commit hook.

## install_dev_tools

Installs required packages for deploying and testing Pelorus inside virtual environment.

## pre-commit

A pre-commit hook for git. Will lint helm charts, and check if formatting is correct.

## bump-version

Bumps the patch version of the given charts.

## chart-lint

Lints helm charts.

## chart-check-and-bump

Lints helm charts, attempting to bump their versions if required.

## python-version-check.py

Used by the makefile to check if the python version is valid.

Not meant to be used directly.

## lib

Contains common code used by python scripts.

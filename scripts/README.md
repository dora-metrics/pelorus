# Scripts

Various scripts for development reside here.

## bump-version

Bumps the patch version of the given charts.

## chart-check-and-bump

Lints helm charts, attempting to bump their versions if required.

## chart-lint

Lints helm charts.

## create_release_pr

Prepares pull request that is used to create Pelorus release

## install_dev_tools

Installs required packages for deploying and testing Pelorus inside virtual environment.

## lib

Contains common code used by python scripts.

## pre-commit

A pre-commit hook for git. Will lint helm charts, and check if formatting is correct.

## python-version-check.py

Used by the makefile to check if the python version is valid.

Not meant to be used directly.

## run-mockoon-tests

Used to create mockoon pod on the localhost and then runs mockoon tests

for the commit time exporter using mocked data from mockoon server.

## setup-pre-commit-hook

Used by the makefile to setup pre-commit hook for local lint tests that are

invoked before commit is prepared.

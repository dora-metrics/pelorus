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

## run-pelorus-e2e-tests

Used to create pelorus namespace, deploy pelorus via helm charts and

run some e2e tests using todolist-mongo-go project from konveyor/mig-demo-apps.

## run-mockoon-tests

Used to create mockoon pod on the localhost and then runs mockoon tests

for the commit time exporter using mocked data from mockoon server.

## setup-pre-commit-hook

Used by the makefile to setup pre-commit hook for local lint tests that are

invoked before commit is prepared.

## scripts/pelorus-operator-patches

Used to create Pelorus helm based operator from the helm charts.

Ensures modification to the operator files can be cleanly applied and allows
to recreate operator easily.

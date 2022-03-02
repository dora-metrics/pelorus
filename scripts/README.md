# Scripts

Various scripts for development reside here.

## setup-dev-env

Sets up a python3.9 virtual environment, installs dependencies, and sets up the pre-commit hook.

## pre-commit

A pre-commit hook for git. Will lint helm charts, and check if formatting is correct.

## bump-version

Bumps the patch version of the given charts.

## chart-lint

Lints helm charts.

## chart-check-and-bump

Lints helm charts, attempting to bump their versions if required.

## lib

Contains common code used by python scripts.

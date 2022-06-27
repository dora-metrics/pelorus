# Variable setup and preflight checks

# may override with environment variable
PYTHON_BINARY?=python3

ifndef PELORUS_VENV
  PELORUS_VENV=.venv
endif

ifeq (, $(shell which $(PYTHON_BINARY) ))
  $(error "PYTHON=$(PYTHON_BINARY) binary not found in $(PATH)")
endif

SYS_PYTHON_VER=$(shell $(PYTHON_BINARY) -c 'from sys import version_info; \
  print("%d.%d" % version_info[0:2])')
$(info Found system python version: $(SYS_PYTHON_VER));
PYTHON_VER_CHECK=$(shell $(PYTHON_BINARY) scripts/python-version-check.py)

ifneq ($(strip $(PYTHON_VER_CHECK)),)
  $(error $(PYTHON_VER_CHECK). You may set the PYTHON_BINARY env var to specify a compatible version)
endif

CHART_TEST=$(shell which ct)

SHELLCHECK=$(shell which shellcheck)
SHELL_SCRIPTS=./demo/demo-tekton \
       scripts/create_release_pr \
       scripts/install_dev_tools \
       scripts/pre-commit \
       scripts/run-mockoon-tests \
       scripts/setup-pre-commit-hook \
       scripts/run-pelorus-e2e-tests

.PHONY: default
default: \
  dev-env

.PHONY: all
all: default

# note the following is required for the makefile help
## TARGET: DESCRIPTION
## ------: -----------
## help: print each make target with a description
.PHONY: help
help:
	@echo ""
	@(printf ""; sed -n 's/^## //p' Makefile) | column -t -s :


# Environment setup

$(PELORUS_VENV): exporters/requirements.txt exporters/requirements-dev.txt
	test -d ${PELORUS_VENV} || ${PYTHON_BINARY} -m venv ${PELORUS_VENV}
	. ${PELORUS_VENV}/bin/activate && \
	       pip install -U pip && \
	       pip install -r exporters/requirements.txt \
	                   -r exporters/requirements-dev.txt
	touch ${PELORUS_VENV}

.PHONY: exporters
exporters: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	       pip install -e exporters/

.PHONY: git-blame
git-blame:
	@echo "⎇ Configuring git to ignore certain revs for annotations"
	$(eval IGNORE_REVS_FILE = $(shell git config blame.ignoreRevsFile))
	if [ "$(IGNORE_REVS_FILE)" != ".git-blame-ignore-revs" ]; then \
		git config blame.ignoreRevsFile .git-blame-ignore-revs; \
	fi

.git/hooks/pre-commit: scripts/pre-commit
	./scripts/setup-pre-commit-hook

## cli_dev_tools: install all necessary CLI dev tools
.PHONY: cli_dev_tools
cli_dev_tools:
	./scripts/install_dev_tools -v $(PELORUS_VENV)

## dev-env: set up everything needed for development (install tools, set up virtual environment, git configuration)
dev-env: $(PELORUS_VENV) cli_dev_tools exporters git-blame \
         .git/hooks/pre-commit
	$(info **** To run VENV: $$source ${PELORUS_VENV}/bin/activate)
	$(info **** To later deactivate VENV: $$deactivate)

# Release

.PHONY: release minor-release major-release

release:
	./scripts/create_release_pr

minor-release:
	./scripts/create_release_pr -i

major-release:
	./scripts/create_release_pr -m

.PHONY: mockoon-tests
mockoon-tests: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/run-mockoon-tests

# End to end tests
## e2e-tests: installs pelorus, mongo-todolist and tests commit and deploy exporters
## e2e-tests-scenario-1: run e2e-tests with latest quay images
## e2e-tests-scenario-2: run e2e-tests for deploytime exporter using different exporter install methods
.PHONY: e2e-tests e2e-tests-scenario-1 e2e-tests-scenario-1
e2e-tests: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/run-pelorus-e2e-tests -o konveyor -e failure

e2e-tests-scenario-1: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/run-pelorus-e2e-tests -f "periodic/quay_images_latest.yaml"

e2e-tests-scenario-2: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/run-pelorus-e2e-tests "periodic/different_deployment_methods.yaml"

# Integration tests
## integration-tests: pytest -rap -m integration
.PHONY: integration-tests
integration-tests: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	coverage run -m pytest -rap -m "integration" && \
	coverage report

# Unit tests
## unit-tests: pytest everything minus integration and mockoon
.PHONY: unit-tests
unit-tests: $(PELORUS_VENV)
  # -r: show extra test summaRy: (a)ll except passed, (p)assed
  # because using (A)ll includes stdout
  # -m filters out integration tests
	. ${PELORUS_VENV}/bin/activate && \
	coverage run -m pytest -rap -m "not integration and not mockoon" && \
	coverage report

# Prometheus ruels
## test-prometheusrules: test prometheus with data in _test/test_promethusrules
.PHONY: test-prometheusrules
test-prometheusrules: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	./_test/test_prometheusrules

# Conf tests
## conf-tests: execute _test/conftest.sh
.PHONY: conf-tests
conf-tests: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	./_test/conftest.sh

# Formatting

.PHONY: format black isort format-check black-check isort-check
format: $(PELORUS_VENV) black isort

## format-check: check that all python code is properly formatted
format-check: $(PELORUS_VENV) black-check isort-check

black: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	black exporters scripts

black-check: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	black --check exporters scripts

isort: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	isort exporters scripts

isort-check: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	isort --check exporters scripts


# Linting

.PHONY: lint pylava chart-lint chart-lint-optional shellcheck shellcheck-optional
## lint: lint python code, shell scripts, and helm charts
lint: pylava chart-lint-optional shellcheck-optional

pylava: $(PELORUS_VENV)
	@echo 🐍 🌋 Linting with pylava
	. ${PELORUS_VENV}/bin/activate && \
	pylava

# chart-lint allows us to fail properly when run from CI,
# while chart-lint-optional allows graceful degrading when
# devs don't have it installed.

# shellcheck follows a similar pattern, but is not currently set up for CI.

chart-lint: $(PELORUS_VENV)
	./scripts/install_dev_tools -v $(PELORUS_VENV) -c ct && \
	. ${PELORUS_VENV}/bin/activate && \
	ct lint --config ct.yaml

ifneq (, $(CHART_TEST))
chart-lint-optional: chart-lint
else
chart-lint-optional:
	$(warning chart test (ct) not installed, skipping)
endif

shellcheck:
	@echo "🐚 📋 Linting shell scripts with shellcheck"
	$(SHELLCHECK) $(SHELL_SCRIPTS)

ifneq (, $(SHELLCHECK))
shellcheck-optional: shellcheck
else
shellcheck-optional:
	$(warning 🐚 ⏭ Shellcheck not found, skipping)
endif


# Testing
.PHONY: test

# -r: show extra test summaRy: (a)ll except passed, (p)assed
# because using (A)ll includes stdout
# -m filters out integration tests
test: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && pytest -r ap -m "not integration"

# Cleanup

## clean-dev-env: remove the virtual environment and clean up all .pyc files
clean-dev-env:
	rm -rf ${PELORUS_VENV}
	find . -iname "*.pyc" -delete

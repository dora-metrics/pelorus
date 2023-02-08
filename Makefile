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
# Sync with .github/workflows/shellcheck.yaml
SHELL_SCRIPTS=demo/demo-tekton.sh \
       scripts/create_release_pr \
       scripts/install_dev_tools \
       scripts/run-mockoon-tests \
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

$(PELORUS_VENV): exporters/requirements.txt exporters/requirements-dev.txt docs/requirements.txt
	test -d ${PELORUS_VENV} || ${PYTHON_BINARY} -m venv ${PELORUS_VENV}
	. ${PELORUS_VENV}/bin/activate && \
	       pip install -U pip && \
	       pip install -r exporters/requirements.txt \
	                   -r exporters/requirements-dev.txt \
					   -r docs/requirements.txt
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

pre-commit-setup: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	pre-commit install

## cli_dev_tools: install all necessary CLI dev tools
.PHONY: cli_dev_tools
cli_dev_tools: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
		./scripts/install_dev_tools -v $(PELORUS_VENV)


# for installing a single CLI dev tool
$(PELORUS_VENV)/bin/%: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
		./scripts/install_dev_tools -v $(PELORUS_VENV) -c $(notdir $@)

# system-level doc requirements
ifeq (Darwin, $(shell uname -s))
/opt/homebrew/Cellar/%:
	brew install $(notdir $@)

system-doc-deps: /opt/homebrew/Cellar/libffi /opt/homebrew/Cellar/cairo
else
system-doc-deps:
endif

## dev-env: set up everything needed for development (install tools, set up virtual environment, git configuration)
dev-env: $(PELORUS_VENV) cli_dev_tools exporters git-blame \
         pre-commit-setup
	$(info **** To run VENV: $$source ${PELORUS_VENV}/bin/activate)
	$(info **** To later deactivate VENV: $$deactivate)

.PHONY: e2e-tests-dev-env
## e2e-tests-dev-env: set up environment required to run e2e tests
e2e-tests-dev-env: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/install_dev_tools -v $(PELORUS_VENV) -c oc,helm
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
e2e-tests: e2e-tests-dev-env
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/run-pelorus-e2e-tests -o konveyor -e failure,gitlab_committime,gitea_committime,bitbucket_committime,jira_committime,jira_custom_committime -t

e2e-tests-scenario-1: e2e-tests-dev-env
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/run-pelorus-e2e-tests -f "periodic/quay_images_latest.yaml" -o konveyor -e failure,gitlab_committime,gitea_committime,bitbucket_committime,jira_committime,jira_custom_committime -t

e2e-tests-scenario-2: e2e-tests-dev-env
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/run-pelorus-e2e-tests -f "periodic/different_deployment_methods.yaml"

# Integration tests
## integration-tests: pytest everything marked as integration
.PHONY: integration-tests
integration-tests: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	pytest -rap -m "integration"

# Unit tests
## unit-tests: pytest everything minus integration and mockoon
.PHONY: unit-tests
unit-tests: $(PELORUS_VENV)
  # -r: show extra test summaRy: (a)ll except passed, (p)assed
  # because using (A)ll includes stdout
  # -m filters out integration tests
	. ${PELORUS_VENV}/bin/activate && \
	pytest -rap -m "not integration and not mockoon"

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
	black exporters scripts docs

black-check: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	black --check exporters scripts docs

isort: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	isort exporters scripts docs

isort-check: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	isort --check exporters scripts docs


# Linting

.PHONY: lint python-lint pylava chart-lint chart-lint-optional shellcheck shellcheck-optional chart-check-bump typecheck
## lint: lint python code, shell scripts, and helm charts
lint: python-lint chart-lint-optional shellcheck-optional

## python-lint: lint python files
python-lint: $(PELORUS_VENV)
	@echo 🐍 🦙 Linting with pylama
	. ${PELORUS_VENV}/bin/activate && \
	pylama

pylava: python-lint

typecheck: $(PELORUS_VENV)
	$(warning Type checking is not fully ready yet, the issues below may be ignorable)
	. ${PELORUS_VENV}/bin/activate && \
	pyright

# chart-lint allows us to fail properly when run from CI,
# while chart-lint-optional allows graceful degrading when
# devs don't have it installed.

# shellcheck follows a similar pattern, but is not currently set up for CI.

## chart-check-bump: lint helm charts, attempting to bump their versions if required
chart-check-bump: $(PELORUS_VENV)
	./scripts/install_dev_tools -v $(PELORUS_VENV) -c ct && \
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/chart-check-and-bump

chart-lint: $(PELORUS_VENV) $(PELORUS_VENV)/bin/ct $(PELORUS_VENV)/bin/helm
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/chart-test.sh

ifneq (, $(CHART_TEST))
chart-lint-optional: chart-lint
else
chart-lint-optional:
	$(warning chart test (ct) not installed, skipping)
endif

shellcheck: $(PELORUS_VENV) $(PELORUS_VENV)/bin/shellcheck
	. ${PELORUS_VENV}/bin/activate && \
	if [[ -z shellcheck ]]; then echo "Shellcheck is not installed" >&2; false; fi && \
	echo "🐚 📋 Linting shell scripts with shellcheck" && \
	shellcheck $(SHELL_SCRIPTS)

ifneq (, $(SHELLCHECK))
shellcheck-optional: shellcheck
else
shellcheck-optional:
	$(warning 🐚 ⏭ Shellcheck not found, skipping)
endif

## doc-check: Check if there is any problem with the project documentation generation
doc-check: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && mkdocs build --verbose --strict

## pre-commit-all: Runs pre-commit library against all files of the project
pre-commit-all: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	pre-commit run --all-files

# Cleanup

## clean-dev-env: remove the virtual environment and clean up all .pyc files
clean-dev-env:
	rm -rf ${PELORUS_VENV}
	find . -iname "*.pyc" -delete

PYTHON_BINARY?=python3

ifndef PELORUS_VENV
  PELORUS_VENV=.venv
endif

ifeq (, $(shell which $(PYTHON_BINARY)))
  $(error "PYTHON=$(PYTHON_BINARY) binary not found in $(PATH)")
endif

SYS_PYTHON_VER=$(shell $(PYTHON_BINARY) -c 'from sys import version_info; print("%d.%d" % version_info[0:2])')
SYS_PYTHON=$(shell $(PYTHON_BINARY) -c 'from sys import executable; print(executable)')
$(info Python version: $(SYS_PYTHON_VER) (from $(SYS_PYTHON)));
PYTHON_VER_CHECK=$(shell $(PYTHON_BINARY) scripts/python-version-check.py)

ifneq ($(strip $(PYTHON_VER_CHECK)),)
  $(error $(PYTHON_VER_CHECK). You may set the PYTHON_BINARY env var to specify a compatible version)
endif

## TARGET: DESCRIPTION
## ------: -----------
## help: Print each available command's description
.PHONY: help
help:
	@echo ""
	@(printf ""; sed -n 's/^## //p' Makefile) | column -t -s :


# Environment setup
$(PELORUS_VENV): exporters/requirements.txt exporters/requirements-dev.txt docs/requirements.txt
	${PYTHON_BINARY} -m venv ${PELORUS_VENV}
	. ${PELORUS_VENV}/bin/activate && \
	       pip install -U pip && \
	       pip install -r exporters/requirements.txt \
	                   -r exporters/requirements-dev.txt \
					   -r docs/requirements.txt && \
		   pip install -e exporters/

# Install a single tool in virtual environment
$(PELORUS_VENV)/bin/%: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
		./scripts/install_dev_tools.sh -v $(PELORUS_VENV) -c $(notdir $@)

# Install all necessary tools in virtual environment
.PHONY: cli_dev_tools
cli_dev_tools: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
		./scripts/install_dev_tools.sh -v $(PELORUS_VENV)

.PHONY: git-blame
git-blame:
	@echo "⎇ Configuring git to ignore certain revs for annotations"
	$(eval IGNORE_REVS_FILE = $(shell git config blame.ignoreRevsFile))
	if [ "$(IGNORE_REVS_FILE)" != ".git-blame-ignore-revs" ]; then \
		git config blame.ignoreRevsFile .git-blame-ignore-revs; \
	fi

.PHONY: pre-commit-setup
pre-commit-setup: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	pre-commit install

# system-level doc requirements
ifeq (Darwin, $(shell uname -s))
/opt/homebrew/Cellar/%:
	brew install $(notdir $@)

system-doc-deps: /opt/homebrew/Cellar/libffi /opt/homebrew/Cellar/cairo
else
system-doc-deps:
endif

## dev-env: Set up development environment
.PHONY: dev-env
dev-env: $(PELORUS_VENV) cli_dev_tools git-blame pre-commit-setup
	$(info IMPORTANT: To activate Python virtual environment, run: source ${PELORUS_VENV}/bin/activate)
	$(info IMPORTANT: To later deactivate Python virtual environment, run: deactivate)

.PHONY: e2e-tests-dev-env
e2e-tests-dev-env: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/install_dev_tools.sh -v $(PELORUS_VENV) -c oc,helm

## e2e-tests: Run E2E (end to end) tests
.PHONY: e2e-tests
e2e-tests: e2e-tests-dev-env
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/run-pelorus-e2e-tests.sh -o konveyor -a -t

## e2e-tests-scenario-1: Run E2E (end to end) tests with image tag latest
.PHONY: e2e-tests-scenario-1
e2e-tests-scenario-1: e2e-tests-dev-env
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/run-pelorus-e2e-tests.sh -f "periodic/quay_images_latest.yaml" -o konveyor -a -t

## e2e-tests-scenario-2: Run E2E (end to end) tests for different exporter install methods
.PHONY: e2e-tests-scenario-2
e2e-tests-scenario-2: e2e-tests-dev-env
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/run-pelorus-e2e-tests.sh -f "periodic/different_deployment_methods.yaml"

## integration-tests: Run Python files integration tests
.PHONY: integration-tests
integration-tests: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	pytest -rap -m "integration"

## mockoon-tests: Run Python files Mockoon tests
.PHONY: mockoon-tests
mockoon-tests: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/run-mockoon-tests.sh

## unit-tests: Run Python files unit tests
.PHONY: unit-tests
unit-tests: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	pytest -rap -m "not integration and not mockoon"

## test-prometheusrules: Test Prometheus rules and Grafana dashboards
.PHONY: test-prometheusrules
test-prometheusrules: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	./_test/test_prometheusrules.sh

## conf-tests: Test OpenShift resources
.PHONY: conf-tests
conf-tests: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	./_test/conftest.sh

## typecheck: Check if objects are correctly typed in Python files
.PHONY: typecheck
typecheck: $(PELORUS_VENV)
	$(warning Type checking is not fully ready yet, the issues below may be ignorable)
	. ${PELORUS_VENV}/bin/activate && \
	pyright

## python-lint: Lint Python files
.PHONY: python-lint
python-lint: $(PELORUS_VENV)
	@echo 🐍 🦙 Linting with pylama
	. ${PELORUS_VENV}/bin/activate && \
	pylama

## shellcheck: Lint shell scripts
.PHONY: shellcheck
shellcheck: $(PELORUS_VENV) $(PELORUS_VENV)/bin/shellcheck
	@echo 🐚 📋 Linting shell scripts with shellcheck
	. ${PELORUS_VENV}/bin/activate && \
	shellcheck $(shell find . -name '*.sh' -type f | grep -v 'venv/\|git/\|.pytest_cache/\|htmlcov/\|_test/test_helper/\|_test/bats\|_test/conftest')

## chart-check: Checks Helm charts validation and format, and all project versions
PHONY: chart-check
chart-check: $(PELORUS_VENV) $(PELORUS_VENV)/bin/ct $(PELORUS_VENV)/bin/helm
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/chart-check.sh

## format: Format all Python files
.PHONY: format
format: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	black . && isort .

## format-check: Check if all Python files are properly formatted
.PHONY: format-check
format-check: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	black --check . && isort --check .

## doc-check: Check if there is any problem with the project documentation generation
.PHONY: doc-check
doc-check: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && mkdocs build --verbose --strict

## pre-commit-all: Run pre-commit library against all files of the project
.PHONY: pre-commit-all
pre-commit-all: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	pre-commit run --all-files

## update-requirements: Update project's Python dependencies files. Requires Poetry executable
.PHONY: update-requirements
update-requirements: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	poetry export --format requirements.txt --output docs/requirements.txt --only doc && \
	poetry export --format requirements.txt --output exporters/requirements-dev.txt --only dev && \
	poetry export --format requirements.txt --output exporters/requirements.txt

## openshift-check-versions: Check if OpenShift versions used by the project are the 4 latest minor stable releases
.PHONY: openshift-check-versions
openshift-check-versions: $(PELORUS_VENV)
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/check_openshift_version.py

## clean-dev-env: Clean up development environment
.PHONY: clean-dev-env
clean-dev-env:
	rm -rf ${PELORUS_VENV}
	find . -iname "*.pyc" -delete

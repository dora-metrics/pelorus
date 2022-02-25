# Variable setup and preflight checks

# Minimal python version supported by exporters
PYTHON_BINARY=python3
PYTHON_VER_MIN=3.9
PYTHON_VER_MAX=3.10.2

ifndef PELORUS_VENV
  PELORUS_VENV=.venv
endif

ifeq (, $(shell which $(PYTHON_BINARY) ))
  $(error "PYTHON=$(PYTHON_BINARY) binary not found in $(PATH)")
endif

SYS_PYTHON_VER=$(shell $(PYTHON_BINARY) -c 'from sys import version_info; \
  from pkg_resources import packaging; \
  print(packaging.version.parse("%d.%d.%d" % version_info[0:3]))')
$(info Found system python version: $(SYS_PYTHON_VER));
PYTHON_VER=$(shell $(PYTHON_BINARY) -c 'from pkg_resources import packaging; \
  print("%s" % (packaging.version.parse("$(PYTHON_VER_MAX)") >= \
  packaging.version.parse("$(SYS_PYTHON_VER)") >= \
  packaging.version.parse("$(PYTHON_VER_MIN)")))')

ifeq ($(PYTHON_VER), False)
  $(error $(PYTHON_BINARY) needs to be at >= $(PYTHON_VER_MIN)\
                           and <= $(PYTHON_VER_MAX))
endif

CHART_TEST=$(shell which ct)

SHELLCHECK=$(shell which shellcheck)
SHELL_SCRIPTS=./scripts/pre-commit ./scripts/setup-pre-commit-hook ./demo/demo-tekton


.PHONY: default
default: \
  dev-env
  
.PHONY: all
all: default


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

.PHONY: cli_dev_tools
cli_dev_tools:
	./scripts/install_dev_tools -v $(PELORUS_VENV)

dev-env: $(PELORUS_VENV) cli_dev_tools exporters git-blame \
         .git/hooks/pre-commit
	$(info **** To run VENV: $$source ${PELORUS_VENV}/bin/activate)
	$(info **** To later deactivate VENV: $$deactivate)


# Formatting

.PHONY: format black isort format-check black-check isort-check
format: $(PELORUS_VENV) black isort 

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
	. ${PELORUS_VENV}/bin/activate && \
	./scripts/chart-lint

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


# Cleanup

clean-dev-env:
	rm -rf ${PELORUS_VENV}
	find -delete . -iname "*.pyc"

# Minimal python version supported by exporters
PYTHON_BINARY=python3
PYTHON_VER_MIN=3.9

ifndef PELORUS_VENV
  PELORUS_VENV=.venv
endif

ifeq (, $(shell command -v $(PYTHON_BINARY) ))
  $(error "PYTHON=$(PYTHON_BINARY) binary not found in $(PATH)")
endif

SYS_PYTHON_VER=$(shell $(PYTHON_BINARY) -c 'from sys import version_info; \
  from pkg_resources import packaging; \
  print(packaging.version.parse("%d.%d.%d" % version_info[0:3]))')
$(info Found system python version: $(SYS_PYTHON_VER));
PYTHON_VER=$(shell $(PYTHON_BINARY) -c 'from pkg_resources import packaging; \
  print("%s" % (packaging.version.parse("$(SYS_PYTHON_VER)") >= \
  packaging.version.parse("$(PYTHON_VER_MIN)")))')

ifeq ($(PYTHON_VER), False)
  $(error $(PYTHON_BINARY) needs to be at >= $(PYTHON_VER_MIN))
endif

.PHONY: default
default: \
  dev-env
  
.PHONY: all
all: default

$(PELORUS_VENV): exporters/requirements.txt exporters/requirements-dev.txt
	test -d ${PELORUS_VENV} || ${PYTHON_BINARY} -m venv ${PELORUS_VENV}
	source ${PELORUS_VENV}/bin/activate && \
	       pip install -U pip && \
	       pip install -r exporters/requirements.txt \
	                   -r exporters/requirements-dev.txt
	touch ${PELORUS_VENV}

.PHONY: exporters
exporters: $(PELORUS_VENV)
	source ${PELORUS_VENV}/bin/activate && \
	       pip install -e exporters/

dev-env: $(PELORUS_VENV) exporters
	$(info **** To run VENV: $$source ${PELORUS_VENV}/bin/activate)
	$(info **** To later deactivate VENV: $$deactivate)

.PHONY: format
format: $(PELORUS_VENV)
	source ${PELORUS_VENV}/bin/activate && \
	./scripts/format;

.PHONY: format-check
format-check: $(PELORUS_VENV)
	source ${PELORUS_VENV}/bin/activate && \
	./scripts/format --check;

.PHONY: pylava
pylava: $(PELORUS_VENV)
	source ${PELORUS_VENV}/bin/activate && \
	pylava;

clean-dev-env:
	rm -rf ${PELORUS_VENV}
	find -delete . -iname "*.pyc"

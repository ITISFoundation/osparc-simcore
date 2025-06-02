#
# These are COMMON target and recipes to Makefiles for **packages/ and services/**
#
# This file is included at the top of every Makefile
#
# $(CURDIR) in this file refers to the directory where this file is included
#
# SEE https://mattandre.ws/2016/05/makefile-inheritance/
#

#
# GLOBALS
#

# defaults
.DEFAULT_GOAL := help

# Colors
BLUE=\033[0;34m
GREEN=\033[0;32m
YELLOW=\033[0;33m
RED=\033[0;31m
NC=\033[0m # No Color

# Use bash not sh
SHELL := /bin/bash

# Some handy flag variables
ifeq ($(filter Windows_NT,$(OS)),)
IS_WSL  := $(if $(findstring Microsoft,$(shell uname -a)),WSL,)
IS_OSX  := $(filter Darwin,$(shell uname -a))
IS_LINUX:= $(if $(or $(IS_WSL),$(IS_OSX)),,$(filter Linux,$(shell uname -a)))
endif
IS_WIN  := $(strip $(if $(or $(IS_LINUX),$(IS_OSX),$(IS_WSL)),,$(OS)))

$(if $(IS_WIN),\
$(error Windows is not supported in all recipes. Use WSL instead. Follow instructions in README.md),)

# version control
VCS_URL       := $(shell git config --get remote.origin.url)
VCS_REF       := $(shell git rev-parse --short HEAD)
NOW_TIMESTAMP := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
REPO_BASE_DIR := $(shell git rev-parse --show-toplevel)

# relevant repo folders
SCRIPTS_DIR := $(abspath $(REPO_BASE_DIR)/scripts)
PACKAGES_DIR := $(abspath $(REPO_BASE_DIR)/packages)
SERVICES_DIR := $(abspath $(REPO_BASE_DIR)/services)

# virtual env
EXPECTED_PYTHON_VERSION := $(shell cat $(REPO_BASE_DIR)/requirements/PYTHON_VERSION)
VENV_DIR      := $(abspath $(REPO_BASE_DIR)/.venv)

# environment variables files
DOT_ENV_FILE = $(abspath $(REPO_BASE_DIR)/.env)

# utils
get_my_ip := $(shell (hostname --all-ip-addresses || hostname -i) 2>/dev/null | cut --delimiter=" " --fields=1)

IGNORE_DIR=.ignore

$(IGNORE_DIR): # Used to produce .ignore folders which are auto excluded from version control (see .gitignore)
	mkdir -p $(IGNORE_DIR)

#
# SHORTCUTS
#

MAKE_C := $(MAKE) --no-print-directory --directory

#
# COMMON TASKS
#


.PHONY: hel%
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
hel%:
	@echo "usage: make [target] ..."
	@echo ""
	@echo "Targets for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""


.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)


.PHONY: devenv
devenv: ## build development environment
	@$(MAKE_C) $(REPO_BASE_DIR) $@


.PHONY: clean
_GIT_CLEAN_ARGS = -dxf -e .vscode
clean: ## cleans all unversioned files in project and temp files create by this makefile
	# Cleaning unversioned
	@git clean -n $(_GIT_CLEAN_ARGS)
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo -n "$(shell whoami), are you REALLY sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@git clean $(_GIT_CLEAN_ARGS)




.PHONY: info
inf%: ## displays basic info
	# system
	@echo ' OS               : $(IS_LINUX)$(IS_OSX)$(IS_WSL)$(IS_WIN)'
	@echo ' CURDIR           : ${CURDIR}'
	@echo ' NOW_TIMESTAMP    : ${NOW_TIMESTAMP}'
	@echo ' VCS_URL          : ${VCS_URL}'
	@echo ' VCS_REF          : ${VCS_REF}'
	# installed in .venv
	@uv pip list
	# package setup
	-@echo ' name         : ' $(shell python ${CURDIR}/setup.py --name)
	-@echo ' version      : ' $(shell python ${CURDIR}/setup.py --version)
	-@echo ' authors      : ' "$(shell python ${CURDIR}/setup.py --author)"
	-@echo ' description  : ' "$(shell python ${CURDIR}/setup.py --description)"



.PHONY: codeformat
codeformat: ## runs all code formatters. Use AFTER make install-*
	@$(eval PYFILES=$(shell find $(CURDIR) -type f -name '*.py'))
	@pre-commit run pyupgrade --files $(PYFILES)
	@pre-commit run pycln --files $(PYFILES)
	@pre-commit run isort --files $(PYFILES)
	@pre-commit run black --files $(PYFILES)


.PHONY: pyupgrade
pyupgrade: ## upgrades python syntax for newer versions of the language (SEE https://github.com/asottile/pyupgrade)
	@pre-commit run pyupgrade --files $(shell find $(CURDIR) -type f -name '*.py')


.PHONY: pylint
pylint: $(REPO_BASE_DIR)/.pylintrc ## runs pylint (python linter) on src and tests folders
	@pylint --rcfile="$(REPO_BASE_DIR)/.pylintrc" -v $(CURDIR)/src $(CURDIR)/tests


.PHONY: doc-uml
doc-uml: $(IGNORE_DIR) ## Create UML diagrams for classes and modules in current package. e.g. (export DOC_UML_PATH_SUFFIX="services*"; export DOC_UML_CLASS=models_library.api_schemas_catalog.services.ServiceGet; make doc-uml)
	@pyreverse \
		--verbose \
		--output=svg \
		--output-directory=$(IGNORE_DIR) \
		--project=$(if ${PACKAGE_NAME},${PACKAGE_NAME},${SERVICE_NAME})${DOC_UML_PATH_SUFFIX} \
		$(if ${DOC_UML_CLASS},--class=${DOC_UML_CLASS},) \
		${SRC_DIR}$(if ${DOC_UML_PATH_SUFFIX},/${DOC_UML_PATH_SUFFIX},)
	@echo Outputs in $(realpath $(IGNORE_DIR))


.PHONY: ruff
ruff: $(REPO_BASE_DIR)/.ruff.toml ## runs ruff (python fast linter) on src and tests folders
	@ruff check \
		--config=$(REPO_BASE_DIR)/.ruff.toml \
		--respect-gitignore \
		$(CURDIR)/src \
		$(CURDIR)/tests

.PHONY: mypy
mypy: $(REPO_BASE_DIR)/mypy.ini ## runs mypy python static type-checker on this services's code. Use AFTER make install-*
	@mypy \
	--config-file=$(REPO_BASE_DIR)/mypy.ini \
	--show-error-context \
	--show-traceback \
	$(CURDIR)/src


.PHONY: codestyle
codestyle codestyle-ci: ## enforces codestyle (isort & black) finally runs pylint & mypy
	@$(SCRIPTS_DIR)/codestyle.bash $(if $(findstring -ci,$@),ci,development) $(shell basename "${SRC_DIR}")

.PHONY: github-workflow-job
github-workflow-job: ## runs a github workflow job using act locally, run using "make github-workflow-job job=JOB_NAME"
	# running job "${job}"
	$(SCRIPTS_DIR)/act.bash ../.. ${job}



.PHONY: version-patch version-minor version-major
version-patch: ## commits version with bug fixes not affecting the cookiecuter config
	$(_bumpversion)
version-minor: ## commits version with backwards-compatible API addition or changes (i.e. can replay)
	$(_bumpversion)
version-major: ## commits version with backwards-INcompatible addition or changes
	$(_bumpversion)


.PHONE: pip-freeze
pip-freeze: ## dumps current environ and base.txt [diagnostics]
	pip freeze > freeze-now.ignore.txt
	cat requirements/_base.txt | grep -v '#' > freeze-base.ignore.txt


#
# SUBTASKS
#

.PHONY: _check_python_version _check_venv_active

_check_python_versio%:
	# Checking that runs with correct python version
	@python3 -c "import sys; current_version=[int(d) for d in '$(EXPECTED_PYTHON_VERSION)'.split('.')]; assert sys.version_info[:2]==tuple(current_version[:2]), f'Expected python $(EXPECTED_PYTHON_VERSION), got {sys.version_info}'"


_check_venv_active: _check_python_version
	# Checking whether virtual environment was activated
	@python3 -c "import sys; assert sys.base_prefix!=sys.prefix"


define _bumpversion
	# Upgrades as $(subst version-,,$@) version, commits and tags
	@bump2version --verbose --list $(subst version-,,$@)
endef

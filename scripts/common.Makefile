#
# These are common target and recipes to Makefiles of packages/ and services/
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

# virtual env
VENV_DIR      := $(abspath $(REPO_BASE_DIR)/.venv)

#
# SHORTCUTS
#

MAKE_C := $(MAKE) --no-print-directory --directory

#
# COMMON TASKS
#


.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help:
	@echo "usage: make [target] ..."
	@echo ""
	@echo "Targets for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""


.PHONY: devenv
devenv: ## build development environment (using main services/docker-compose-build.yml)
	@$(MAKE_C) $@


.PHONY: clean
_GIT_CLEAN_ARGS = -dxf -e .vscode
clean: ## cleans all unversioned files in project and temp files create by this makefile
	# Cleaning unversioned
	@git clean -n $(_GIT_CLEAN_ARGS)
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo -n "$(shell whoami), are you REALLY sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@git clean $(_GIT_CLEAN_ARGS)


.PHONY: info
info: ## displays basic info
	# system
	@echo ' OS               : $(IS_LINUX)$(IS_OSX)$(IS_WSL)$(IS_WIN)'
	@echo ' CURDIR           : ${CURDIR}'
	@echo ' NOW_TIMESTAMP    : ${NOW_TIMESTAMP}'
	@echo ' VCS_URL          : ${VCS_URL}'
	@echo ' VCS_REF          : ${VCS_REF}'
	# installed in .venv
	@pip list
	# package
	-@echo ' name         : ' $(shell python ${CURDIR}/setup.py --name)
	-@echo ' version      : ' $(shell python ${CURDIR}/setup.py --version)



.PHONY: autoformat
autoformat: ## runs black python formatter on this service's code. Use AFTER make install-*
	# sort imports
	@python3 -m isort --verbose \
		--atomic \
		--recursive \
		--skip-glob */client-sdk/* \
		--skip-glob */migration/* \
		$(CURDIR)
	# auto formatting with black
	@python3 -m black --verbose \
		--exclude "/(\.eggs|\.git|\.hg|\.mypy_cache|\.nox|\.tox|\.venv|\.svn|_build|buck-out|build|dist|migration|client-sdk|generated_code)/" \
		$(CURDIR)

.PHONY: mypy
mypy: $(REPO_BASE_DIR)/scripts/mypy.bash $(REPO_BASE_DIR)/mypy.ini ## runs mypy python static type checker on this services's code. Use AFTER make install-*
	@$(REPO_BASE_DIR)/scripts/mypy.bash src

.PHONY: code-analysis
code-analysis: $(REPO_BASE_DIR)/.codeclimate.yml ## runs code-climate analysis
	# Copying config
	cp $(REPO_BASE_DIR)/.codeclimate.yml $(CURDIR)/.codeclimate.yml
	# Validates $< at ${PWD}
	$(REPO_BASE_DIR)/scripts/code-climate.bash validate-config
	# Running analysis
	$(REPO_BASE_DIR)/scripts/code-climate.bash analyze
	# Removing tmp config
	@-rm $(CURDIR)/.codeclimate.yml


.PHONY: version-patch version-minor version-major
version-patch: ## commits version with bug fixes not affecting the cookiecuter config
	$(_bumpversion)
version-minor: ## commits version with backwards-compatible API addition or changes (i.e. can replay)
	$(_bumpversion)
version-major: ## commits version with backwards-INcompatible addition or changes
	$(_bumpversion)


buil%: ## builds docker image (using main services/docker-compose-build.yml)
	# building docker image for ${APP_NAME}
	@$(MAKE_C) ${REPO_BASE_DIR} build target=${APP_NAME}

# FIXME:
#.PHONY: build build-nc build-devel build-devel-nc build-cache build-cache-nc
#build build-nc build-devel build-devel-nc build-cache build-cache-nc: ## docker image build in many flavours
#	# building docker image for ${APP_NAME} ...
#	@$(MAKE_C) ${REPO_BASE_DIR} $@ target=${APP_NAME}

.PHONY: shell
shell: ## runs shell in production container
	@$(MAKE_C) ${REPO_BASE_DIR} shell target=${APP_NAME}

#
# SUBTASKS
#

.PHONY: _check_python_version _check_venv_active

_check_python_version:
	# Checking that runs with correct python version
	@python3 -c "import sys; assert sys.version_info[:2]==(3,6), f'Expected python 3.6, got {sys.version_info}'"


_check_venv_active: _check_python_version
	# checking whether virtual environment was activated
	@python3 -c "import sys; assert sys.base_prefix!=sys.prefix"


define _bumpversion
	# upgrades as $(subst version-,,$@) version, commits and tags
	@bump2version --verbose --list $(subst version-,,$@)
endef

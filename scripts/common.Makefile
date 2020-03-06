#
# These are common target and recipes
# This file is included at the top of every Makefile
# $(CURDIR) in this file refers to the directory where this file is included
#
# SEE https://mattandre.ws/2016/05/makefile-inheritance/
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


#
# COMMON TASKS
#


.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '$(notdir $(CURDIR))':"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""


deven%: ## build development environment (using main services/docker-compose-build.yml)
	@$(MAKE) --directory ${REPO_BASE_DIR} --no-print-directory $@


GIT_CLEAN_ARGS = -dxf -e .vscode
clea%: ## cleans all unversioned files in project and temp files create by this makefile
	# Cleaning unversioned
	@git clean -n $(GIT_CLEAN_ARGS)
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo -n "$(shell whoami), are you REALLY sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@git clean $(GIT_CLEAN_ARGS)



inf%: ## displays basic info
	# installed
	@pip list
	# version
	@cat setup.py | grep name=
	@cat setup.py | grep version=


.PHONY: autoformat
autoformat: ## runs black python formatter on this service's code [https://black.readthedocs.io/en/stable/]
	# auto formatting with black
	@python3 -m black --verbose \
		--exclude "/(\.eggs|\.git|\.hg|\.mypy_cache|\.nox|\.tox|\.venv|\.svn|_build|buck-out|build|dist|migration|client-sdk)/" \
		$(CURDIR)


.PHONY: version-patch version-minor version-major
version-patch: ## commits version with bug fixes not affecting the cookiecuter config
	$(_bumpversion)
version-minor: ## commits version with backwards-compatible API addition or changes (i.e. can replay)
	$(_bumpversion)
version-major: ## commits version with backwards-INcompatible addition or changes
	$(_bumpversion)


buil%: ## builds docker image (using main services/docker-compose-build.yml)
	# building docker image for ${APP_NAME}
	@$(MAKE) --directory ${REPO_BASE_DIR} --no-print-directory target=${APP_NAME} build


#
# SUBTASKS
#

.PHONY: _check_venv_active
_check_venv_active:
	# checking whether virtual environment was activated
	@python3 -c "import sys; assert sys.base_prefix!=sys.prefix"


define _bumpversion
	# upgrades as $(subst version-,,$@) version, commits and tags
	@bump2version --verbose --list $(subst version-,,$@)
endef

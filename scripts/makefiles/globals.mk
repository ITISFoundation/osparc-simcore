#
# GLOBALS, platform detection, common variables and venv-check subtasks.
#
# LIBRARY (.mk): include-only, not a directly-invoked entry point.
# Included (transitively via common.mk) at the top of every package/service Makefile.
# $(CURDIR) here refers to the directory of the top-level Makefile that includes it.
# SEE scripts/makefiles/README.md for conventions.
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
include $(REPO_BASE_DIR)/scripts/makefiles/templates.mk

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
# SUBTASKS
#

.PHONY: _check_python_version _check_venv_active

# spellchecker:ignore-next-line
_check_python_versio%:
	# Checking that runs with correct python version
	@python3 -c "import sys; current_version=[int(d) for d in '$(EXPECTED_PYTHON_VERSION)'.split('.')]; assert sys.version_info[:2]==tuple(current_version[:2]), f'Expected python $(EXPECTED_PYTHON_VERSION), got {sys.version_info}'"


_check_venv_active: _check_python_version
	# Checking whether virtual environment was activated
	@python3 -c "import sys; assert sys.base_prefix!=sys.prefix"

#
# Common targets and recipes for packages/
#
# LIBRARY (.mk): include-only, not a directly-invoked entry point.
# USAGE (top of a package Makefile):
#   include ../../scripts/makefiles/common.mk
#   include ../../scripts/makefiles/package.mk
#
# $(CURDIR) here refers to the package directory that includes it.
# SEE scripts/makefiles/README.md for conventions.
#

# NOTE $(CURDIR) in this file refers to the directory where this file is included

# Variable based on conventions (override if they do not apply)
PACKAGE_NAME      = $(notdir $(CURDIR))
PY_PACKAGE_NAME  = $(subst -,_,$(PACKAGE_NAME))
PACKAGE_VERSION  := $(shell cat VERSION)
SRC_DIR           = $(abspath $(CURDIR)/src/$(PY_PACKAGE_NAME))

export PACKAGE_VERSION


#
# TEST TASKS
#

PYTEST_COV_TARGET ?= $(PY_PACKAGE_NAME)
PYTEST_ASYNCIO_ARGS ?= --asyncio-mode=auto
PYTEST_JUNIT_ARGS ?= --junitxml=junit.xml -o junit_family=legacy
TEST_TARGET ?= $(CURDIR)/tests

PYTEST_BASE_ARGS ?= \
	$(PYTEST_ASYNCIO_ARGS) \
	--color=yes \
	--cov-config=../../.coveragerc \
	--cov-report=term-missing \
	--cov=$(PYTEST_COV_TARGET) \
	--durations=10

PYTEST_ARGS_dev ?= \
	--exitfirst \
	--failed-first \
	--pdb \
	-vv

PYTEST_ARGS_ci ?= \
	--cov-append \
	--cov-report=xml \
	$(PYTEST_JUNIT_ARGS) \
	--log-date-format="%Y-%m-%d %H:%M:%S" \
	--log-format="%(asctime)s %(levelname)s %(message)s" \
	--verbose \
	-m "not heavy_load"

include $(REPO_BASE_DIR)/scripts/makefiles/python-test.mk


.PHONY: test test-ci-unit test-dev-unit

# Canonical package test targets. Historical package targets delegate here.
test-ci-unit: _run-test-ci ## runs package unit tests in CI mode

test-dev-unit: _run-test-dev ## runs package unit tests for development (e.g. w/ pdb)

test: test-dev-unit ## runs package unit tests for development (e.g. w/ pdb)


#
# COMMON TASKS
#

.PHONY: info
info: ## displays package info
	@make --no-print-directory info-super
	# package env vars
	@echo ' PACKAGE_VERSION      : ${PACKAGE_VERSION}'


#
# SUBTASKS
#


# ---------------------------------------------------------------------------
# i18n — extract translatable strings for this package
# ---------------------------------------------------------------------------
include $(REPO_BASE_DIR)/scripts/makefiles/i18n.mk

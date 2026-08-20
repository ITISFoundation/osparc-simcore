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
# NOTE: shared install-*/tests/tests-ci/requirements recipes are intentionally
# NOT provided here yet: the per-package recipes have drifted (e.g. celery-library
# uses --keep-docker-up, common-library omits --junitxml and has a custom
# install-dev that compiles .mo files). Reconciling that drift needs a per-package
# decision. SEE scripts/makefiles/README.md ("Known follow-ups").
#

# NOTE $(CURDIR) in this file refers to the directory where this file is included

# Variable based on conventions (override if they do not apply)
PACKAGE_NAME      = $(notdir $(CURDIR))
PY_PACKAGE_NAME  = $(subst -,_,$(PACKAGE_NAME))
PACKAGE_VERSION  := $(shell cat VERSION)
SRC_DIR           = $(abspath $(CURDIR)/src/$(PY_PACKAGE_NAME))

export PACKAGE_VERSION


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

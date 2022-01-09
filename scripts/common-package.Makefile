#
# These are common target and recipes to Makefiles for packages/
#
# USAGE: Add this in the top of package's Makefile
#
#   include ../../scripts/common.Makefile
#   include ../../scripts/common-package.Makefile
#

#
# GLOBALS
#

# NOTE $(CURDIR) in this file refers to the directory where this file is included

# Variable based on conventions (override if they do not apply)
PACKAGE_NAME      = $(notdir $(CURDIR))
PY_PACKAGE_NAME  = $(subst -,_,$(PACKAGE_NAME))
PACKAGE_VERSION  := $(shell cat VERSION)
SRC_DIR           = $(abspath $(CURDIR)/src/$(PY_PACKAGE_NAME))

export PACKAGE_VERSION


#
# SHORTCUTS
#


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

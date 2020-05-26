# Recipes to upgrade requirements in batch
#
# Examples of usage
#
# - Full upgrade of all packages
#  	make touch packages
#
# - Upgrade one library in all packages
#   make packages upgrade=name-of-package
#
#
# WARNING: USE CAREFULLY. STILL UNDER DEVELOPMENT
#
.DEFAULT_GOAL := help

# locations
REPODIR := $(abspath $(CURDIR)/../..)
PACKAGES_DIR := $(abspath $(REPODIR)/packages)

UPGRADE_OPTION := $(if $(upgrade),upgrade=$(upgrade),)

# tools
MAKE_C := $(MAKE) --no-print-directory --directory


.PHONY: touch reqs
# packages/
_input-requirements = $(shell find ${PACKAGES_DIR} -type f -name _base.in)
# api tests
_input-requirements += $(shell find $(REPODIR)/api/tests/ -type f -name *.in)
# system tests
_input-requirements += $(shell find $(REPODIR)/tests/ -type f -name *.in)


$(info Found $(_input-requirements))


touch: ## touches all package requirement inputs
	$(foreach p,${_input-requirements},touch $(p);)

reqs: ## updates requirements of all package libraries
	$(foreach p,${_input-requirements},touch $(p); $(MAKE_C) $(dir $(p)) reqs $(UPGRADE_OPTION);)


.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

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
# WARNING: this batch MUST ONLY be used for non-services. Services are INDEPENDENT
#          and to upgrade them, use services/{servicesname}/requirements/Makefile
#
.DEFAULT_GOAL := help

# locations
REPODIR := $(shell git rev-parse --show-toplevel)
PACKAGES_DIR := $(abspath $(REPODIR)/packages)
SERVICES_DIR := $(abspath $(REPODIR)/services)

UPGRADE_OPTION := $(if $(upgrade),upgrade=$(upgrade),)

# tools
MAKE_C := $(MAKE) --directory


.PHONY: touch reqs _check_py36_version

# requirements in packages and services
_compiled-all = $(shell find $(REPODIR) -path "*/requirements/*.txt")
_inputs-all = $(shell find $(REPODIR) -path "*/requirements/*.in")

# packages/
_target-inputs = $(shell find ${PACKAGES_DIR} -type f -name _base.in)
# api tests
_target-inputs += $(shell find $(REPODIR)/api/tests/ -type f -name "*.in")
# system tests
_target-inputs += $(shell find $(REPODIR)/tests/ -type f -name "*.in")
# services tests libraries, tools and fixtures
_target-inputs += $(shell find ${SERVICES_DIR} -type f -name "_test.in")

$(info Found $(words $(_target-inputs)) inputs)


_check_py36_version:
	# Checking that runs with correct python version
	@python3 -c "import sys; assert sys.version_info[:2]==(3,6), f'Expected python 3.6, got {sys.version_info}'"


touch: ## touches all package requirement inputs
	# First aligns time-stamps: ensures compiled timestamp is older than target inputs
	@$(foreach p,${_inputs-all},touch $(p);)
	@$(foreach p,${_compiled-all},touch $(p);)
	# Touchs all target input requirements
	@$(foreach p,${_target-inputs},touch $(p);)

reqs: _check_py36_version ## updates requirements of all package libraries
	# Upgrading $(upgrade) requirements
	@$(foreach p,${_target-inputs},echo Touching $(p);touch $(p);$(MAKE_C) $(dir $(p)) reqs $(UPGRADE_OPTION);)


# SEE https://medium.com/faun/set-current-host-user-for-docker-container-4e521cef9ffc
.PHONY: build
build build-nc:
	docker build $(if $(findstring -nc,$@),--no-cache,) --tag local/python-devkit:latest .


.PHONY: run
run: build ## Runs upgrade in a container
	docker run -it \
		--workdir="/home/$(USER)" \
    --volume="/etc/group:/etc/group:ro" \
    --volume="/etc/passwd:/etc/passwd:ro" \
    --volume="/etc/shadow:/etc/shadow:ro" \
		--volume=$(REPODIR):/home/$(USER) \
		--user=$(shell id -u):$(shell id -g) \
		--entrypoint=/bin/bash \
		local/python-devkit:latest \
		-c "cd requirements/tools; make reqs $(if $(upgrade),upgrade=$(upgrade),)"


.PHONY: shell
shell:
	docker run -it \
		--workdir="/home/$(USER)/requirements/tools" \
    --volume="/etc/group:/etc/group:ro" \
    --volume="/etc/passwd:/etc/passwd:ro" \
		--volume="/etc/shadow:/etc/shadow:ro" \
		--volume=$(REPODIR):/home/$(USER) \
		--user=$(shell id -u):$(shell id -g) \
		--entrypoint=/bin/bash \
		local/python-devkit:latest


.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

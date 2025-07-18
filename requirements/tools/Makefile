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

PYTHON_VERSION=3.11.9

# locations
REPODIR := $(shell git rev-parse --show-toplevel)
PACKAGES_DIR := $(abspath $(REPODIR)/packages)
SERVICES_DIR := $(abspath $(REPODIR)/services)

IMAGE := local/requirements/tools

UPGRADE_OPTION := $(if $(upgrade),upgrade=$(upgrade),)
STARTSWITH_OPTION := $(if $(startswith),startswith=$(startswith),)
UPGRADE_OR_STARTSWITH_OPTION := $(if $(upgrade),upgrade=$(upgrade),$(if $(startswith),startswith=$(startswith),))
UPGRADE_OR_STARTSWITH_OR_CLEAN_OPTION := $(if $(upgrade),upgrade=$(upgrade),$(if $(startswith),startswith=$(startswith),$(if $(clean),clean=$(clean),)))

# tools
MAKE_C := $(MAKE) --directory


.PHONY: touch reqs info

# requirements in packages and services
_all-txt = $(shell find $(REPODIR) -path "*/requirements*.txt")
_all-in := $(shell find ${REPODIR} -path "*/requirements*.in" | sort)
_tools-in := $(shell find ${REPODIR} -path "*/requirements/*tools.in" | sort)
_services-in := $(shell find ${SERVICES_DIR} -path "*/requirements*.in" | sort)


# packages/
_target-inputs = $(shell find ${PACKAGES_DIR} -type f -name _base.in)
# api tests
_target-inputs += $(shell find $(REPODIR)/api/tests/ -type f -name "*.in")
# system tests
_target-inputs += $(shell find $(REPODIR)/tests/ -type f -name "*.in")
# services tests libraries, tools and fixtures
_target-inputs += $(shell find ${SERVICES_DIR} -type f -name "_test.in")


info: ## displays some info
	# dev tools version
	@echo ' make   : $(shell make --version 2>&1 | head -n 1)'
	@echo ' jq     : $(shell jq --version 2> /dev/null || echo missing)'
	@echo ' awk    : $(shell awk -W version 2>&1 | head -n 1)'
	@echo ' node   : $(shell node --version 2> /dev/null || echo missing)'
	@echo ' python : $(shell python3 --version)'
	# installed in .venv
	@pip list
	# target reqs found
	@echo "Found $(words $(_target-inputs)) inputs"


touch: ## touches all package requirement inputs
	# First aligns time-stamps: ensures compiled timestamp is older than target inputs
	@$(foreach p,${_all-txt},touch $(p);)
	@$(foreach p,${_all-in},touch $(p);)
	# Touchs all target input requirements
	@$(foreach p,${_target-inputs},touch $(p);)

only-tools: ## upgrades tools repo wide
	# Upgrading ONLY _tools.in
	@$(foreach p,${_tools-in},echo Touching $(p);touch $(p);$(MAKE_C) $(dir $(p)) reqs $(UPGRADE_OR_STARTSWITH_OR_CLEAN_OPTION);)

reqs: guard-UPGRADE_OR_STARTSWITH_OR_CLEAN_OPTION ## updates test & tooling requirements
	# Upgrading $(upgrade)$(startswith)$(if $(clean), cleaning) requirements
	@$(foreach p,${_target-inputs},echo Touching $(p);touch $(p);$(MAKE_C) $(dir $(p)) reqs $(UPGRADE_OR_STARTSWITH_OR_CLEAN_OPTION);)


reqs-all: guard-UPGRADE_OR_STARTSWITH_OR_CLEAN_OPTION ## updates a given package or pattern repository-wise IN ALL `requirements/` folders (e.g. make reqs-all upgrade=foo==1.2.3 or make reqs-all startswith=pytest or make reqs-all clean=1)
	# Upgrading $(upgrade)$(startswith)$(if $(clean), cleaning) ALL requirements
	@$(foreach p,${_all-in},echo Touching $(p);touch $(p);$(MAKE_C) $(dir $(p)) reqs $(UPGRADE_OR_STARTSWITH_OR_CLEAN_OPTION);)

reqs-services: guard-UPGRADE_OR_STARTSWITH_OR_CLEAN_OPTION ## updates a given package or pattern on all services [and not packages] (e.g. make reqs-services upgrade=foo==1.2.3 or make reqs-services startswith=pytest or make reqs-services clean=1)
	# Upgrading $(upgrade)$(startswith)$(if $(clean), cleaning) in services
	@$(foreach p,${_services-in},echo Touching $(p);touch $(p);$(MAKE_C) $(dir $(p)) reqs $(UPGRADE_OR_STARTSWITH_OR_CLEAN_OPTION);)


reqs-ci: ## upgrades requirements for pylint recipe in CI
	cd $(REPODIR)/ci/helpers \
	&& rm requirements.txt \
	&& uv pip compile --resolver=backtracking --strip-extras requirements.in

IMAGE_NAME:=local/python-devkit:${PYTHON_VERSION}

# SEE https://medium.com/faun/set-current-host-user-for-docker-container-4e521cef9ffc
.PHONY: build
build build-nc: ## builds tooling image ${IMAGE_NAME}
	docker buildx build $(if $(findstring -nc,$@),--no-cache,) \
		--load \
		--build-arg PYTHON_VERSION="${PYTHON_VERSION}" \
		--tag ${IMAGE_NAME} .


.PHONY: run
run: build ## Runs upgrade in a container [WARNING! UNDER DEV. USE CAREFULY]
	docker run -it \
		--workdir="/home/$(USER)" \
		--volume="/etc/group:/etc/group:ro" \
    --volume="/etc/passwd:/etc/passwd:ro" \
		--volume=$(REPODIR):/home/$(USER) \
		--user=$(shell id -u):$(shell id -g) \
		--entrypoint=/bin/bash \
		${IMAGE_NAME} \
		-c "cd requirements/tools; make reqs $(UPGRADE_OR_STARTSWITH_OR_CLEAN_OPTION)"


.PHONY: shell
shell: build ## Opens shell in ${IMAGE_NAME}
	docker run -it \
		--workdir="/home/$(USER)/requirements/tools" \
		--volume="/etc/group:/etc/group:ro" \
    --volume="/etc/passwd:/etc/passwd:ro" \
		--volume=$(REPODIR):/home/$(USER) \
		--user=$(shell id -u):$(shell id -g) \
		--entrypoint=/bin/bash \
		${IMAGE_NAME}


.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Examples:"
	@echo "  make reqs                                # Upgrade all test & tooling requirements"
	@echo "  make reqs upgrade=pytest                 # Upgrade only pytest package in test & tooling"
	@echo "  make reqs startswith=pytest              # Upgrade all packages starting with 'pytest' in test & tooling"
	@echo "  make reqs clean=1                        # Clean and rebuild all test & tooling requirements"
	@echo ""
	@echo "  make reqs-all upgrade=fastapi            # Upgrade fastapi in ALL requirements files"
	@echo "  make reqs-all startswith=pydantic        # Upgrade all packages starting with pydantic repo-wide"
	@echo "  make reqs-all clean=1                    # Clean and rebuild ALL requirements"
	@echo ""
	@echo "  make reqs-services upgrade=uvicorn       # Upgrade uvicorn only in services"
	@echo "  make reqs-services startswith=sqlalchemy # Upgrade all packages starting with sqlalchemy in services folder"
	@echo ""
	@echo "  make only-tools upgrade=black            # Upgrade black only in tools requirements"
	@echo ""


.PHONY: guard-%
guard-%:
	@if [ "${${*}}" = "" ]; then echo "Environment variable $* not set"; exit 1; fi


.PHONY: report
report: ## generates a report of updated requirements that shall be pasted in the PR
	@python check_changes.py --changed-reqs > report.ignore.md
	@python check_changes.py >> report.ignore.md
	@cat report.ignore.md
	@echo SEE $(shell realpath report.ignore.md)

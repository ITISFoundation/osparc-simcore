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

PYTHON_VERSION:=3.8.10

# locations
REPODIR      := $(shell git rev-parse --show-toplevel)
PACKAGES_DIR := $(abspath $(REPODIR)/packages)
SERVICES_DIR := $(abspath $(REPODIR)/services)
APP_NAME     :=$(notdir $(CURDIR))
IMAGE_NAME   :=local/${APP_NAME}-devkit:${PYTHON_VERSION}

# tools
MAKE_C := $(MAKE) --directory


# SEE https://medium.com/faun/set-current-host-user-for-docker-container-4e521cef9ffc
.PHONY: build
build build-nc: ## builds tooling image ${IMAGE_NAME}
	docker build $(if $(findstring -nc,$@),--no-cache,) \
		--build-arg PYTHON_VERSION="${PYTHON_VERSION}" \
		--build-arg HOME_DIR="/home/$(USER)" \
		--tag ${IMAGE_NAME} \
		.


.PHONY: shell
shell: build ## Mounts REPODIR and open shell in ${IMAGE_NAME} (mostly for interactive debug/use)
	# pydeps docs https://pydeps.readthedocs.io/en/latest/#usage
	docker run -it \
		--workdir="/home/$(USER)/osparc-simcore" \
		--volume="/etc/group:/etc/group:ro" \
		--volume="/etc/passwd:/etc/passwd:ro" \
		--volume=$(REPODIR):/home/$(USER)/osparc-simcore \
		--user=$(shell id -u):$(shell id -g) \
		--entrypoint=/bin/bash \
		${IMAGE_NAME}

# Examples:
#  - SEE  https://pydeps.readthedocs.io/en/latest/#usage
#
# pydeps services/web/server/src/simcore_service_webserver --only "simcore_service_webserver.projects" --no-show --cluster
#
#
#


.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""


.PHONY: guard-%
guard-%:
	@if [ "${${*}}" = "" ]; then echo "Environment variable $* not set"; exit 1; fi

# osparc-simcore base image builder makefile
#
# NOTES:
# 	- GNU make version 4.2 recommended
# 	- Use 'make -n *' to dry-run during debugging
# 	- In windows, only WSL is supported
#
# by sanderegg, pcrespov
#
.DEFAULT_GOAL := help

SHELL := /bin/bash

MAKE_C := $(MAKE) --no-print-directory --directory

# version control
export VCS_URL          := $(shell git config --get remote.origin.url)
export VCS_REF          := $(shell git rev-parse HEAD)
export VCS_REF_CLIENT   := $(shell git log --pretty=tformat:"%h" -n1 services/static-webserver/client)
export VCS_STATUS_CLIENT:= $(if $(shell git status -s),'modified/untracked','clean')
export BUILD_DATE       := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

# version tags
export DOCKER_IMAGE_TAG ?= latest
export DOCKER_REGISTRY  ?= itisfoundation


.PHONY: help

help: ## help on rule's targets
ifeq ($(IS_WIN),)
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
else
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
endif

.PHONY: build build-push

build build-push: ## Builds base docker images used in osparc-simcore stack
	# Building base images
	@docker buildx bake --file=docker-compose.base.yml $($(findstring -push,$@),--push, --load)
	# Building builder images
	@docker buildx bake --file=docker-compose.builder.yml $($(findstring -push,$@),--push, --load)
	# List images
	@docker images --filter="reference=local/osparc-*"

info: ## Shows info about the built docker images
	@docker images --filter="reference=local/osparc-*"

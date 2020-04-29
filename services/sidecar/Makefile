#
# Targets for DEVELOPMENT of Components Catalog Service
#
include ../../scripts/common.Makefile


APP_NAME     := sidecar
APP_CLI_NAME := simcore-service-sidecar
export APP_VERSION = $(shell cat VERSION)

REPO_BASE_DIR  = $(abspath $(CURDIR)/../../)
VENV_DIR      ?= $(abspath $(REPO_BASE_DIR)/.venv)


.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: requirements _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	# FIXME: pip-sync does not manage to install storage-sdk
	# pip-sync requirements/$(subst install-,,$@).txt
	pip install -r requirements/$(subst install-,,$@).txt


.PHONY: tests-unit tests-integration tests
tests: tests-unit tests-integration

tests-unit: ## runs unit tests
	# running unit tests
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests/unit

tests-integration: ## runs integration tests against local+production images
	# running integration tests local/(service):production images ...
	@export DOCKER_REGISTRY=local; \
	export DOCKER_IMAGE_TAG=production; \
	pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests/integration


.PHONY: build build-nc build-devel build-devel-nc build-cache build-cache-nc
build build-nc build-devel build-devel-nc build-cache build-cache-nc: ## docker image build in many flavours
	# building ${APP_NAME} ...
	@$(MAKE_C) ${REPO_BASE_DIR} $@ target=${APP_NAME}

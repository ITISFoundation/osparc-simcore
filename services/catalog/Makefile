#
# Targets for DEVELOPMENT of Components Catalog Service
#

# Makefile config
.DEFAULT_GOAL := help
SHELL = /bin/bash

# Custom variables
APP_NAME     := $(notdir $(CURDIR))
APP_CLI_NAME := simcore-service-catalog
export APP_VERSION = $(shell cat VERSION)

REPO_BASE_DIR  = $(abspath $(CURDIR)/../../)
VENV_DIR      ?= $(abspath $(REPO_BASE_DIR)/.venv)


.PHONY: devenv
devenv: ## build development environment (using main services/docker-compose-build.yml)
	@$(MAKE) --directory ${REPO_BASE_DIR} $@


.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE) --directory requirements all


.check-venv-active:
	# checking whether virtual environment was activated
	@python3 -c "import sys; assert sys.base_prefix!=sys.prefix"

.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: requirements .check-venv-active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


PHONY: tests-unit tests-integration tests

tests: tests-unit tests-integration

tests-unit: ## runs unit tests
	# running unit tests
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests/unit

tests-integration: ## runs integration tests against local+production images
	# running integration tests local/(service):production images ...
	@export DOCKER_REGISTRY=local; \
	export DOCKER_IMAGE_TAG=production; \
	pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests/integration


.PHONY: run-devel down-pg up-pg
run-devel run-prod: up-pg ## runs app with pg service
	# starting service ...
ifeq ($(subst run-,,$@),devel)
	# development mode (with reload upon change)
	uvicorn simcore_service_catalog.main:app --reload
else
	# production mode
	simcore-service-catalog
endif
	# stop


up-pg: down-pg
	# starting pg database ...
	docker-compose -f $(CURDIR)/tests/unit/with_dbs/docker-compose.yml up --detach

down-pg: ## stops pg fixture
	docker-compose -f $(CURDIR)/tests/unit/with_dbs/docker-compose.yml down


.PHONY: build build-nc build-devel build-devel-nc build-cache build-cache-nc
build build-nc build-devel build-devel-nc build-cache build-cache-nc: ## docker image build in many flavours
	# building ${APP_NAME} ...
	@$(MAKE) --directory ${REPO_BASE_DIR} $@ target=${APP_NAME}


.PHONY: autoformat
autoformat: ## runs black python formatter on this service's code [https://black.readthedocs.io/en/stable/]
	# auto formatting with black
	@python3 -m black --verbose $(CURDIR)


.PHONY: openapi-specs
openapi-specs: install-dev ## TODO: implementing a way to serialize openapi
	python3 -c "from simcore_service_catalog.main import *; dump_openapi()"


define _bumpversion
	# upgrades as $(subst version-,,$@) version, commits and tags
	@bump2version --verbose --list $(subst version-,,$@)
endef

version-patch: ## commits version with bug fixes not affecting the cookiecuter config
	$(_bumpversion)
version-minor: ## commits version with backwards-compatible API addition or changes (i.e. can replay)
	$(_bumpversion)
version-major: ## commits version with backwards-INcompatible addition or changes
	$(_bumpversion)


.PHONY: replay

replay: .cookiecutterrc ## re-applies cookiecutter
	# Replaying ../cookiecutter-simcore-py-fastapi/ ...
	@cookiecutter --no-input --overwrite-if-exists \
		--config-file=$< \
		--output-dir="$(abspath $(CURDIR)/..)" \
		"../cookiecutter-simcore-py-fastapi/"


.PHONY: info
info: ## displays information
	# installed
	@pip list
	# version
	@cat VERSION


.PHONY: clean clean-all
git_clean_args = -dxf -e .vscode

clean: ## cleans all unversioned files in project and temp files create by this makefile
	# Cleaning unversioned
	@git clean -n $(git_clean_args)
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo -n "$(shell whoami), are you REALLY sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@git clean $(git_clean_args)


#-----------------------------------
.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

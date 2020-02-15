#
# Targets for DEVELOPMENT of Public API Gateway
#

# Makefile config
.DEFAULT_GOAL := help
SHELL = /bin/bash

# Custom variables
APP_NAME     := $(notdir $(CURDIR))
APP_CLI_NAME := simcore-service-public-api-gateway
export APP_VERSION = $(shell cat VERSION)


REPO_BASE_DIR  = $(CURDIR)

VENV_DIR      ?= $(abspath $(REPO_BASE_DIR)/.venv)

.PHONY: devenv

.venv:
	python3 -m venv $@
	$@/bin/pip3 install --upgrade \
		pip \
		wheel \
		setuptools

devenv: .venv ## create a python virtual environment with dev tools (e.g. linters, etc)
	$</bin/pip3 install \
		pylint \
		autopep8 \
		pip-tools \
		rope
	@echo "To activate the venv, execute 'source .venv/bin/activate'



.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE) --directory requirements all


.PHONY: install-dev install-prod install-ci
.check-venv-active:
	# checking whether virtual environment was activated
	@python3 -c "import sys; assert sys.base_prefix!=sys.prefix"

install-dev install-prod install-ci: requirements .check-venv-active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


PHONY: tests-unit tests-integration
tests-unit: ## runs unit tests
	# running unit tests
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests/unit


tests-integration: ## runs integration tests against local+production images
	# running integration tests local/(service):production images ...
	@export DOCKER_REGISTRY=local; \
	export DOCKER_IMAGE_TAG=production; \
	pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests/integration


.PHONY: run-devel down
run-devel: down ## runs app with pg fixture for development
	# starting pg database ...
	docker-compose -f $(CURDIR)/tests/unit/with_dbs/docker-compose.yml up --detach
	# starting service
	uvicorn simcore_service_catalog.main:app --reload
	# stop

down: ## stops pg fixture
	docker-compose -f $(CURDIR)/tests/unit/with_dbs/docker-compose.yml down




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


.PHONY: clean clean-all
git_clean_args = -dxf -e .vscode

clean: ## cleans all unversioned files in project and temp files create by this makefile
	# Cleaning unversioned
	@git clean -n $(git_clean_args)
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo -n "$(shell whoami), are you REALLY sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@git clean $(git_clean_args)


.PHONY: help
help: ## this colorful help
	@echo "Recipes for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

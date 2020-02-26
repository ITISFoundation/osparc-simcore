#
# TODO: under development
#
.DEFAULT_GOAL := help

APP_NAME     := webserver
APP_CLI_NAME := simcore-service-catalog
export APP_VERSION = $(shell cat VERSION)

REPO_BASE_DIR  = $(abspath $(CURDIR)/../../../)
VENV_DIR      ?= $(abspath $(REPO_BASE_DIR)/.venv)


.PHONY: devenv
devenv: ## build development environment (using main services/docker-compose-build.yml)
	@$(MAKE) --directory ${REPO_BASE_DIR} $@


.PHONY: devenv
devenv: ## build development environment (using main services/docker-compose-build.yml)
	@$(MAKE) -C ${REPO_BASE_DIR} $@


.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE) --directory requirements all


.PHONY: openapi-specs
openapi-specs: ## updates and validates openapi specifications
	$(MAKE) -C $(CURDIR)/src/simcore_service_${APP_NAME}/api $@


.check-venv-active:
	# checking whether virtual environment was activated
	@python3 -c "import sys; assert sys.base_prefix!=sys.prefix"


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: openapi-specs requirements .check-venv-active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@$(VENV_DIR)/bin/pip3 install -r requirements/$(subst install-,,$@).txt


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


.PHONY: run-devel
run-devel: ## runs app with pg service
	# setting up dbs
	@docker-compose -f tests/unit/with_dbs/docker-compose-devel.yml down
	@docker-compose -f tests/unit/with_dbs/docker-compose-devel.yml up --detach
	# Running $(APP_CLI_NAME)
	## $(APP_CLI_NAME) --print-config > config.yaml | sed enable: true enable: false
	$(APP_CLI_NAME)  -c  tests/unit/with_dbs/config-devel.yml




.PHONY: build build-nc build-devel build-devel-nc build-cache build-cache-nc
build build-nc build-devel build-devel-nc build-cache build-cache-nc: openapi-specs ## docker image build in many flavours
	# building ${APP_NAME} ...
	@$(MAKE) --directory ${REPO_BASE_DIR} $@ target=${APP_NAME}


.PHONY: tail
tail: ## tails log of $(APP_NAME) container
	docker logs -f $(shell docker ps -f "name=$(APP_NAME)*" --format {{.ID}}) > $(APP_NAME).log 2>&1



.PHONY: autoformat
autoformat: ## runs black python formatter on this service's code [https://black.readthedocs.io/en/stable/]
	# auto formatting with black
	@python3 -m black --verbose $(CURDIR)

.PHONY: version-patch version-minor
version-patch version-minor: ## commits version as patch (bug fixes not affecting the API), minor/minor (backwards-compatible/INcompatible API addition or changes)
	# upgrades as $(subst version-,,$@) version, commits and tags
	@bump2version --verbose --list $(subst version-,,$@)


.PHONY: info
info: ## displays
	# installed
	@pip list
	# version
	@cat setup.py | grep version=


.PHONY: clean
clean: ## cleans all unversioned files in project and temp files create by this makefile
	# Cleaning unversioned
	@git clean -ndxf -e .vscode/
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo -n "$(shell whoami), are you REALLY sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@git clean -dxf -e .vscode/


.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '${APP_NAME}':"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

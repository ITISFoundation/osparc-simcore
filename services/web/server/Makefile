#
# TODO: under development
#
.DEFAULT_GOAL := help

APP_NAME     := webserver
APP_CLI_NAME  = simcore-service-${APP_NAME}

ROOT_DIR     = $(abspath $(CURDIR)/../../../)
VENV_DIR    ?= $(abspath $(ROOT_DIR)/.venv)


.PHONY: install
install: ## install app in edit mode for development [DEV]
	# installing in edit mode
	@$(VENV_DIR)/bin/pip3 install -r requirements/dev.txt


.PHONY: tests tunit tintegration
tests: tunit tintegration## runs all tests [DEV]
	# All tests run

tunit:
	# running unit tests
	@$(VENV_DIR)/bin/pytest -vv -x --ff --pdb $(CURDIR)/tests/unit


export DOCKER_REGISTRY=local
export DOCKER_IMAGE_TAG=production
tintegration:
	# running integration tests ${DOCKER_REGISTRY}/(service):${DOCKER_IMAGE_TAG} images ...
	@$(VENV_DIR)/bin/pytest -vv -x --ff --pdb $(CURDIR)/tests/integration


.PHONY: build
build: ## builds docker image (using main services/docker-compose-build.yml)
	@$(MAKE) -C ${ROOT_DIR} target=${APP_NAME} build


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

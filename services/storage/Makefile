#
# TODO: under development
#
.DEFAULT_GOAL := help

APP_NAME     := $(dirname $(CURDIR))
APP_CLI_NAME  = simcore-service-${APP_NAME}

ROOT_DIR  = $(abspath $(CURDIR)/../../)
VENV_DIR ?= $(abspath $(ROOT_DIR)/.venv)

API_SPECS_DIR := ${ROOT_DIR}/api/specs/${APP_NAME}/v0
OAS_SOURCES    = $(shell find $(API_SPECS_DIR)/ -type f -name '*.y*ml')
OAS_TARGET    := $(CURDIR)/src/simcore_service_${APP_NAME}/api/openapi.yaml




.PHONY: devenv
devenv: ## build development environment (using main services/docker-compose-build.yml)
	@$(MAKE) -C ${ROOT_DIR} $@


.PHONY: install
install: ## install app in edit mode for development [DEV]
	# installing in edit mode
	@$(VENV_DIR)/bin/pip3 install -r requirements/dev.txt


.PHONY: tests
tests: ## runs all tests [DEV]
	# running unit tests
	@$(VENV_DIR)/bin/pytest -vv -x --ff --pdb $(CURDIR)/tests/unit
	# running integration tests
	@$(VENV_DIR)/bin/pytest -vv -x --ff --pdb $(CURDIR)/tests/integration



.PHONY: build
build: ## builds docker image (using main services/docker-compose-build.yml)
	@$(MAKE) -C ${ROOT_DIR} target=${APP_NAME} $@


# TODO: container with https://www.npmjs.com/package/swagger-cli
${OAS_TARGET}: $(OAS_SOURCES)
	# bundling '${API_SPECS_DIR}' to '${OAS_TARGET}' ...
	swagger-cli bundle -o $@ -t yaml -r "${API_SPECS_DIR}/openapi.yaml"

.PHONY: openapi-specs
openapi-specs: ${OAS_TARGET} ## creates and validates OpenAPI specs
	# Validating bundled '${OAS_TARGET}'
	swagger-cli validate $<



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

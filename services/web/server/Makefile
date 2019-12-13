#
# TODO: under development
#
.DEFAULT_GOAL := help

APP_NAME     := webserver
APP_CLI_NAME  = simcore-service-${APP_NAME}

REPO_BASE_DIR  = $(abspath $(CURDIR)/../../../)
VENV_DIR ?= $(abspath $(REPO_BASE_DIR)/.venv)




.PHONY: devenv
devenv: ## build development environment (using main services/docker-compose-build.yml)
	@$(MAKE) -C ${REPO_BASE_DIR} $@


.PHONY: openapi-specs
openapi-specs: ## updates and validates openapi specifications
	$(MAKE) -C $(CURDIR)/src/simcore_service_webserver/api $@


.PHONY: install
install-dev install-prod install-ci: openapi-specs ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@$(VENV_DIR)/bin/pip3 install -r requirements/$(subst install-,,$@).txt


.PHONY: tests-unit tests-integration
tests-unit: ## runs unit tests
	# running unit tests
	@pytest -vv -x --ff --pdb $(CURDIR)/tests/unit


tests-integration: ## runs integration tests against local+production images
	# running integration tests local/(service):production images ...
	@export DOCKER_REGISTRY=local; \
	export DOCKER_IMAGE_TAG=production; \
	pytest -vv -x --ff --pdb $(CURDIR)/tests/integration


.PHONY: build
build: openapi-specs ## builds docker image (using main services/docker-compose-build.yml)
	@$(MAKE) -C ${REPO_BASE_DIR} target=${APP_NAME} $@


.PHONY: version-patch version-minor version-major
version-patch version-minor version-major: ## commits version as patch (bug fixes not affecting the API), minor/minor (backwards-compatible/INcompatible API addition or changes)
	# upgrades as $(subst version-,,$@) version, commits and tags
	@bump2version --verbose --list $(subst version-,,$@)


.PHONY: info
info: ## displays
	# installed
	@pip list


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
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_- ]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

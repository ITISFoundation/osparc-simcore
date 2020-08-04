#
# Targets for DEVELOPMENT of Components Catalog Service
#
include ../../scripts/common.Makefile

# Custom variables
APP_NAME         := $(notdir $(CURDIR))
APP_CLI_NAME     := simcore-service-catalog
APP_PACKAGE_NAME := $(subst -,_,$(APP_CLI_NAME))
APP_VERSION      := $(shell cat VERSION)
SRC_DIR          := $(abspath $(CURDIR)/src/$(APP_PACKAGE_NAME))

export APP_VERSION

.PHONY: requirements reqs
requirements reqs: ## (or reqs) compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: requirements _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync --quiet requirements/$(subst install-,,$@).txt


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


# DEVELOPMENT ########


.env:
	cp .env-devel $@

docker-compose.yml:
	cp $(CURDIR)/tests/unit/with_dbs/docker-compose.yml $@


.PHONY: run-devel down up-pg

up-pg: docker-compose.yml down-pg
	# starting pg database ...
	docker-compose -f $< up --detach

down-pg: docker-compose.yml ## stops pg fixture
	# stopping extra services
	-@docker-compose -f $< down


run-devel run-prod: .env up-pg ## runs app with pg service
	# starting service ...
ifeq ($(subst run-,,$@),devel)
	# development mode (with reload upon change)
	# start app (under $<)
	uvicorn simcore_service_catalog.__main__:the_app \
		--reload --reload-dir $(SRC_DIR) \
		--port=8000 --host=0.0.0.0
else
	# production mode
	simcore-service-catalog
endif
	# stop


# BUILD #####################

.PHONY: build build-nc build-devel build-devel-nc build-cache build-cache-nc
build build-nc build-devel build-devel-nc build-cache build-cache-nc: ## docker image build in many flavours
	# building ${APP_NAME} ...
	@$(MAKE_C) ${REPO_BASE_DIR} $@ target=${APP_NAME}


.PHONY: openapi-specs openapi.json
openapi-specs: openapi.json
openapi.json:
	# generating openapi specs file
	python3 -c "import json; from $(APP_PACKAGE_NAME).__main__ import *; print( json.dumps(the_app.openapi(), indent=2) )" > $@

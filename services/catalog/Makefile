#
# Targets for DEVELOPMENT of Components Catalog Service
#
include ../../scripts/common.Makefile

# Custom variables
APP_NAME     := $(notdir $(CURDIR))
APP_CLI_NAME := simcore-service-catalog
export APP_VERSION = $(shell cat VERSION)


.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
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
	@$(MAKE_C) ${REPO_BASE_DIR} $@ target=${APP_NAME}


.PHONY: openapi-specs
openapi-specs: install-dev ## TODO: implementing a way to serialize openapi
	python3 -c "from simcore_service_catalog.main import *; dump_openapi()"


.PHONY: replay
replay: .cookiecutterrc ## re-applies cookiecutter
	# Replaying ../cookiecutter-simcore-py-fastapi/ ...
	@cookiecutter --no-input --overwrite-if-exists \
		--config-file=$< \
		--output-dir="$(abspath $(CURDIR)/..)" \
		"../cookiecutter-simcore-py-fastapi/"

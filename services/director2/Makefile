#
# DEVELOPMENT recipes for director2
#
include ../../scripts/common.Makefile

# Custom variables
APP_NAME         := $(notdir $(CURDIR))
APP_CLI_NAME     := simcore-service-director2
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
	@pytest -vv \
		--exitfirst \
		--failed-first \
		--durations=10 \
		--pdb \
		$(CURDIR)/tests/unit

tests-integration: ## runs integration tests against local+production images
	# running integration tests local/(service):production images ...
	@export DOCKER_REGISTRY=local; \
	export DOCKER_IMAGE_TAG=production; \
	pytest -vv \
		--exitfirst \
		--failed-first \
		--durations=10 \
		--pdb \
		$(CURDIR)/tests/integration


# DEVELOPMENT ########
.env:
	cp .env-devel $@

docker-compose-db.ignore.yml: docker-compose-db.yml .env
	# resolving $@ under environ $<
	docker-compose -f $< config > $@



.PHONY: up-db down down-db run-devel

up-db: docker-compose-db.ignore.yml down # starts pg stack fixture
	# starting database stack as defined in  ...
	docker-compose -f $< up --detach

down down-db: docker-compose-db.ignore.yml ## stops pg stack fixture
	# stopping extra services
	-@docker-compose -f $< down

run-devel: .env up-db  ## starts db and start service in host
	# start app (within $<) in devel mode
	uvicorn $(APP_PACKAGE_NAME).__main__:the_app \
		--reload --reload-dir $(SRC_DIR) \
		--port=8000 --host=0.0.0.0


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

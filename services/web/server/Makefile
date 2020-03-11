#
# Targets for DEVELOPMENT for Webserver service
#
include ../../../scripts/common.Makefile

APP_NAME     := webserver
APP_CLI_NAME := simcore-service-catalog
export APP_VERSION = $(shell cat VERSION)

REPO_BASE_DIR  = $(abspath $(CURDIR)/../../../)


.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE) --directory requirements all


.PHONY: openapi-specs
openapi-specs: ## updates and validates openapi specifications
	$(MAKE) -C $(CURDIR)/src/simcore_service_${APP_NAME}/api $@


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: openapi-specs requirements _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	python -m pip install -r requirements/$(subst install-,,$@).txt


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

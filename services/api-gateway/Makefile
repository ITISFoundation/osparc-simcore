#
# Targets for DEVELOPMENT of Public API Gateway
#
include ../../scripts/common.Makefile

# Custom variables
APP_NAME     := $(notdir $(CURDIR))
APP_CLI_NAME := simcore-service-api-gateway
export APP_VERSION = $(shell cat VERSION)


.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE) --directory requirements reqs


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
	uvicorn simcore_service_api_gateway.main:app --reload
	# stop

down: ## stops pg fixture
	docker-compose -f $(CURDIR)/tests/unit/with_dbs/docker-compose.yml down

.PHONY: build
build: ## builds docker image (using main services/docker-compose-build.yml)
	@$(MAKE) --directory ${REPO_BASE_DIR} target=${APP_NAME} $@


.PHONY: replay
replay: .cookiecutterrc ## re-applies cookiecutter
	# Replaying /home/crespo/devp/osparc-simcore/services/api-gateway/../../../cookiecutter-simcore-py-fastapi ...
	@cookiecutter --no-input --overwrite-if-exists \
		--config-file=$< \
		--output-dir="$(abspath $(CURDIR)/..)" \
		"/home/crespo/devp/osparc-simcore/services/api-gateway/../../../cookiecutter-simcore-py-fastapi"

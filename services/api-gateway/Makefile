#
# Targets for DEVELOPMENT of Public API Gateway
#
include ../../scripts/common.Makefile

# Custom variables
APP_NAME     := $(notdir $(CURDIR))
APP_CLI_NAME := simcore-service-api-gateway
export APP_VERSION = $(shell cat VERSION)


.PHONY: reqs
reqs: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


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


# DEVELOPMENT TOOLS ########

.PHONY: run-devel down
run-devel: .env-devel down ## runs app on host with pg fixture for development [for development]
	# running current app
	export $(shell grep -v '^#' $< | xargs  -d '\n'); \
	docker-compose -f $(CURDIR)/tests/utils/docker-compose.yml up --detach; \
	uvicorn simcore_service_api_gateway.main:the_app --reload --port=8001 --host=0.0.0.0

.PHONY: db-tables
db-tables: .env-devel ## upgrades and create tables [for development]
	# Upgrading and creating tables
	export $(shell grep -v '^#' $< | xargs  -d '\n'); \
	python3 tests/utils/init-pg.py

.PHONY: db-migration
db-migration: .env-devel ## runs discover and upgrade on running pg-db [for development]
	# Creating tables
	export $(shell grep -v '^#' $< | xargs  -d '\n'); \
	sc-pg discover && sc-pg upgrade

down: ## stops pg fixture
	# stopping extra services
	-@docker-compose -f $(CURDIR)/tests/utils/docker-compose.yml down
	# killing any process using port 8001
	-@fuser --kill --verbose --namespace tcp 8001

######################


.PHONY: build
build: ## builds docker image (using main services/docker-compose-build.yml)
	@$(MAKE_C) ${REPO_BASE_DIR} target=${APP_NAME} $@


.PHONY: replay
# TODO: replay shall point to online cookiecutter
replay: .cookiecutterrc ## re-applies cookiecutter
	# Replaying /home/crespo/devp/osparc-simcore/services/api-gateway/../../../cookiecutter-simcore-py-fastapi ...
	@cookiecutter --no-input --overwrite-if-exists \
		--config-file=$< \
		--output-dir="$(abspath $(CURDIR)/..)" \
		"/home/crespo/devp/osparc-simcore/services/api-gateway/../../../cookiecutter-simcore-py-fastapi"



# GENERATION python client -------------------------------------------------
.PHONY: python-client generator-help
# SEE https://openapi-generator.tech/docs/usage#generate
# SEE https://openapi-generator.tech/docs/generators/python

# NOTE: assumes this repo exists
GIT_USER_ID := ITISFoundation
GIT_REPO_ID := osparc-simcore-python-client

SCRIPTS_DIR := $(abspath $(CURDIR)/../../scripts)
GENERATOR_NAME := python

# TODO: put instead to additional-props.yaml and --config=openapi-generator/python-config.yaml
ADDITIONAL_PROPS := \
	generateSourceCodeOnly=false\
	hideGenerationTimestamp=true\
	library=urllib3\
	packageName=osparc\
	packageUrl=https://github.com/$(GIT_USER_ID)/${GIT_REPO_ID}.git\
	packageVersion=$(APP_VERSION)\
	projectName=osparc-simcore-python-api
ADDITIONAL_PROPS := $(foreach prop,$(ADDITIONAL_PROPS),$(strip $(prop)))

null  :=
space := $(null) #
comma := ,

# TODO: fix this, shall be generated upon start when flag is provided
openapi.json:
	wget http://localhost:8001/api/v0/openapi.json

# TODO: code_samples still added by hand!
client:
	# cloning $(GIT_USER_ID)/$(GIT_REPO_ID) -> $@
	git clone git@github.com:$(GIT_USER_ID)/$(GIT_REPO_ID).git $@

python-client: openapi.json client ## runs python client generator
	# running python generator on $(word 2,$^)
	cd $(CURDIR); \
	$(SCRIPTS_DIR)/openapi-generator-cli.bash generate \
		--input-spec=/local/$< \
		--generator-name=$(GENERATOR_NAME) \
		--output=/local/$(word 2,$^) \
		--git-user-id=$(GIT_USER_ID)\
		--git-repo-id=$(GIT_REPO_ID)\
		--minimal-update\
		--additional-properties=$(subst $(space),$(comma),$(strip $(ADDITIONAL_PROPS)))\
		--package-name=osparc\
		--release-note="Updated tof $(APP_VERSION)"\
		--remove-operation-id-prefix


generator-help: ## help on client-api generator
	# generate help
	@$(SCRIPTS_DIR)/openapi-generator-cli.bash help generate
	# generator config help
	@$(SCRIPTS_DIR)/openapi-generator-cli.bash config-help -g $(GENERATOR_NAME)

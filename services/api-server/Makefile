#
# Targets for DEVELOPMENT of Public API Server
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

.PHONY: reqs
reqs: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


# DEVELOPMENT TOOLS ###########################################################################

.env:
	cp .env-devel $@

DOCKER_COMPOSE_EXTRA_FILE:=.docker-compose-extra-ignore.yml
$(DOCKER_COMPOSE_EXTRA_FILE):
	cp $(CURDIR)/tests/utils/docker-compose.yml $@


.PHONY: db-tables
db-tables: .env ## upgrades and create tables [for development]
	# Upgrading and creating tables
	export $(shell grep -v '^#' $< | xargs  -d '\n'); \
	python3 tests/utils/init-pg.py



.PHONY: db-migration
db-migration: .env ## runs discover and upgrade on running pg-db [for development]
	# Creating tables
	export $(shell grep -v '^#' $< | xargs  -d '\n'); \
	sc-pg discover && sc-pg upgrade


.PHONY: down
down: $(DOCKER_COMPOSE_EXTRA_FILE)## stops pg fixture
	# stopping extra services
	-@docker-compose -f $< down
	# killing any process using port 8000 (app) and 3000 (debug)
	-@fuser --kill --verbose --namespace tcp 8000
	-@fuser --kill --verbose --namespace tcp 3000


# TODO: These are all different ways to run the server for dev-purposes .

.PHONY: run-devel
run-devel: .env $(DOCKER_COMPOSE_EXTRA_FILE) down
	# Starting db (under $<)
	docker-compose --file $(DOCKER_COMPOSE_EXTRA_FILE)  up --detach
	sleep 2
	# Creating db-tables: user=key, password=secret
	@$(MAKE) db-tables
	# start app (under $<)
	uvicorn simcore_service_api_server.__main__:the_app \
		--reload --reload-dir $(SRC_DIR) \
		--port=8000 --host=0.0.0.0 \
		--log-level debug


.PHONY: run-fake run-fake-devel
run-fake: # starts a fake server in a container
	docker run -it \
		--env-file .env-fake-standalone \
		--publish 8000:8000 \
		local/${APP_NAME}:production
	# Open http://172.0.0.1:8000/dev/doc


run-fake-devel: # starts a fake server in a dev-container
	docker run -it \
		--env-file .env-fake-standalone \
	  --env SC_BOOT_MODE=debug-ptvsd \
    --env LOG_LEVEL=debug \
    --env DEBUG=true \
		--publish 8000:8000 \
		--publish 3006:3000 \
		--volume $(REPO_BASE_DIR)/services/api-server:/devel/services/api-server \
		--volume $(REPO_BASE_DIR)/packages:/devel/packages \
		local/${APP_NAME}:development
	# Open http://172.0.0.1:8000/dev/doc


# BUILD ###########################################################################
# specification of the used openapi-generator-cli (see also https://github.com/ITISFoundation/openapi-generator)
OPENAPI_GENERATOR_NAME := itisfoundation/openapi-generator-cli-openapi-generator-v4.2.3
OPENAPI_GENERATOR_TAG := v0
OPENAPI_GENERATOR_IMAGE := $(OPENAPI_GENERATOR_NAME):$(OPENAPI_GENERATOR_TAG)

define create_and_validate_openapi
	# generating openapi specs file under $< (NOTE: Skips DEV FEATURES since this OAS is the 'offically released'!)
	@source .env; \
	export API_SERVER_DEV_FEATURES_ENABLED=$1; \
	python3 -c "import json; from $(APP_PACKAGE_NAME).main import *; print( json.dumps(the_app.openapi(), indent=2) )" > $@

	# validates OAS file: $@
	docker run --rm \
			--volume "$(CURDIR):/local" \
			$(OPENAPI_GENERATOR_IMAGE) validate --input-spec /local/$@

endef


.PHONY: openapi-specs openapi.json openapi-dev.json

openapi-specs: openapi.json

openapi.json: .env
	@$(call create_and_validate_openapi,0)

openapi-dev.json: .env
	@$(call create_and_validate_openapi,1)

# GENERATION python client ###########################################################################
.PHONY: python-client generator-help python-client-openapi-branch

# NOTE: assumes this repo exists
GIT_USER_ID := ITISFoundation
GIT_CLIENT_REPO_ID := osparc-simcore-python-client
CLIENT_BRANCH := master

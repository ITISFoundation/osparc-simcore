#
# Targets for DEVELOPMENT of comp-resource-manager
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
	uvicorn simcore_service_comp_resource_manager.__main__:the_app \
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
		--volume $(REPO_BASE_DIR)/services/comp-resource-manager:/devel/services/comp-resource-manager \
		--volume $(REPO_BASE_DIR)/packages:/devel/packages \
		local/${APP_NAME}:development
	# Open http://172.0.0.1:8000/dev/doc


# BUILD ###########################################################################

.PHONY: openapi-specs openapi.json
openapi-specs: openapi.json
openapi.json: .env
	# generating openapi specs file
	python3 -c "import json; from $(APP_PACKAGE_NAME).__main__ import *; print( json.dumps(the_app.openapi(), indent=2) )" > $@
	# validates OAS file: $@
	@cd $(CURDIR); \
	$(SCRIPTS_DIR)/openapi-generator-cli.bash validate --input-spec /local/$@

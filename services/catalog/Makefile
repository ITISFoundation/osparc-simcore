#
# Targets for DEVELOPMENT of Components Catalog Service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile


.PHONY: requirements reqs
requirements reqs: ## (or reqs) compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs





# DEVELOPMENT ########

.env:
	cp .env-devel $@


.PHONY: run-devel up-extra down down-extra

up-extra: .env down-extra ## creates and starts adjacent services and migrates postgres database
	# starting all adjacent services
	docker-compose -f docker-compose-extra.yml up --detach
	sleep 1
	# discovering postgres services
	@export $(shell grep -v '^#' .env | xargs) && sc-pg discover
	@sc-pg info
	# upgrading postgres database to HEAD version
	@sc-pg upgrade

down down-extra: docker-compose-extra.yml ## stops pg fixture
	# cleanup discover cache
	-@sc-pg clean
	# stopping extra services
	-@docker-compose -f docker-compose-extra.yml down
	# killing any process using port 8000
	-@fuser --kill --verbose --namespace tcp 8000


run-devel: .env up-extra  ## starts app with extra stack
	# start app (within $<) in devel mode
	uvicorn $(APP_PACKAGE_NAME).__main__:the_app \
		--reload --reload-dir $(SRC_DIR) \
		--port=8000 --host=0.0.0.0

run-prod: .env up-extra
	# start app (within $<) in prod mode
	$(APP_CLI_NAME)



# BUILD #####################


# specification of the used openapi-generator-cli (see also https://github.com/ITISFoundation/openapi-generator)
OPENAPI_GENERATOR_NAME := itisfoundation/openapi-generator-cli-openapi-generator-v4.2.3
OPENAPI_GENERATOR_TAG := v0
OPENAPI_GENERATOR_IMAGE := $(OPENAPI_GENERATOR_NAME):$(OPENAPI_GENERATOR_TAG)


.PHONY: openapi-specs openapi.json
openapi-specs: openapi.json
openapi.json: .env
	# generating openapi specs file
	python3 -c "import json; from $(APP_PACKAGE_NAME).main import *; print( json.dumps(the_app.openapi(), indent=2) )" > $@

	# validates OAS file: $@
	docker run --rm \
			--volume "$(CURDIR):/local" \
			$(OPENAPI_GENERATOR_IMAGE) validate --input-spec /local/$@

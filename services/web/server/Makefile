#
# Targets for DEVELOPMENT for Webserver service
#
include ../../../scripts/common.Makefile
include ../../../scripts/common-service.Makefile

# overrides since it does not has same directory name
APP_NAME := webserver


.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: openapi-specs
openapi-specs: ## updates and validates openapi specifications
	$(MAKE_C) $(CURDIR)/src/simcore_service_${APP_NAME}/api $@



.PHONY: run-devel
run-devel: ## runs app with pg service
	# setting up dbs
	@docker-compose -f tests/unit/with_dbs/docker-compose-devel.yml down
	@docker-compose -f tests/unit/with_dbs/docker-compose-devel.yml up --detach
	# Running $(APP_CLI_NAME)
	## $(APP_CLI_NAME) --print-config > config.yaml | sed enable: true enable: false
	$(APP_CLI_NAME)  -c  tests/unit/with_dbs/config-devel.yml

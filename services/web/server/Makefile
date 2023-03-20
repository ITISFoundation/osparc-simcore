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



_project_models_rest.py: ## auto-generates pydantic model for project rest API model
	# auto-generates $@ from $<
	datamodel-codegen  \
		--input $(CURDIR)/src/simcore_service_webserver/api/v0/schemas/project-v0.0.1.json  \
		--input-file-type jsonschema \
		--snake-case-field \
		--use-schema-description  \
		--output $@



	echo import warnings  >> $@
	echo "warnings.warn('DO NOT USE IN PRODUCTION, STILL UNDER DEVELOPMENT')"  >> $@

	echo ProjectSchema = SimcoreProject >> $@
	# formats and moves
	black $@
	mv $@ src/simcore_service_webserver/projects/$@

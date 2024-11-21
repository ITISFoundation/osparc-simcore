#
# Targets for DEVELOPMENT for Storage service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

APP_OPENAPI_RELPATH=src/$(APP_PACKAGE_NAME)/api/v0/openapi.yaml


.PHONY: openapi-specs
openapi-specs: ## updates and validates openapi specifications
	$(MAKE_C) $(REPO_BASE_DIR)/api/specs/$(APP_NAME) all
	# validates OAS file: $(APP_OPENAPI_RELPATH)
	$(call validate_openapi_specs,$(APP_OPENAPI_RELPATH))


.PHONY: tests
tests: ## runs unit tests
	# running unit tests
	@pytest -vv --asyncio-mode=auto --failed-first --durations=10 --pdb $(CURDIR)/tests


# DEVELOPMENT ########
.env:
	cp .env-devel $@

run-devel: .env
	# start app (within $<) in prod mode
	export $(shell grep -v '^#' .env-devel | xargs -0); \
	$(APP_CLI_NAME)

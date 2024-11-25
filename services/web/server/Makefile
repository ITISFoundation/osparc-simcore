#
# Targets for DEVELOPMENT for Webserver service
#
include ../../../scripts/common.Makefile
include ../../../scripts/common-service.Makefile

# overrides since it does not has same directory name
APP_NAME := webserver
PY_PACKAGE_NAME := simcore_service_webserver

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


APP_OPENAPI_RELPATH=src/$(PY_PACKAGE_NAME)/api/v0/openapi.yaml

.PHONY: openapi-specs
openapi-specs: ## updates and validates openapi specifications
	$(MAKE_C) $(REPO_BASE_DIR)/api/specs/web-server all
	# validates OAS file: $(APP_OPENAPI_RELPATH)
	$(call validate_openapi_specs,$(APP_OPENAPI_RELPATH))

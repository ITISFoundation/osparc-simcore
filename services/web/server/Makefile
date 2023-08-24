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
	$(MAKE_C) $(REPO_BASE_DIR)/api/specs/web-server all

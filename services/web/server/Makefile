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


.PHONY: openapi-specs
openapi-specs: ## updates and validates openapi specifications
	$(MAKE_C) $(REPO_BASE_DIR)/api/specs/web-server all


.PHONY: echo-errors
echo-errors: _check_venv_active ## echo exceptions tree
	@python "${SCRIPTS_DIR}/print_exceptions_tree.py" "${PY_PACKAGE_NAME}" "${PY_PACKAGE_NAME}.errors.WebServerBaseError"

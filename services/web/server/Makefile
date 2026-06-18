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


APP_OPENAPI_RELPATH=src/$(PY_PACKAGE_NAME)/api/v0/openapi.json

.PHONY: openapi-specs
openapi-specs: ## updates and validates openapi specifications
	$(MAKE_C) $(REPO_BASE_DIR)/api/specs/web-server all
	# validates OAS file: $(APP_OPENAPI_RELPATH)
	$(call validate_openapi_specs,$(APP_OPENAPI_RELPATH))


.PHONY: create-admin
create-admin: ## bootstraps the first ADMIN user in the running stack. Usage: make create-admin email=admin@foo.com [product=osparc]
	@$(if $(email),,$(error Missing 'email'. Usage: make create-admin email=admin@foo.com [product=osparc]))
	@container_id=$$(docker ps --filter "name=webserver" --filter "status=running" --format "{{.ID}}" | head -n1); \
	if [ -z "$$container_id" ]; then echo "ERROR: no running webserver container found"; exit 1; fi; \
	docker exec -it "$$container_id" simcore-service-webserver create-admin $(email) --product-name $(or $(product),osparc)

#
# Targets for DEVELOPMENT of Components Catalog Service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile



.env-ignore:
	$(APP_CLI_NAME) echo-dotenv > $@


.PHONY: openapi-specs openapi.json
openapi-specs: openapi.json
openapi.json: .env-ignore
	# generating openapi specs file (need to have the environment set for this)
	@set -o allexport; \
	source $<; \
	set +o allexport; \
	python3 -c "import json; from $(APP_PACKAGE_NAME).main import *; print( json.dumps(app_factory().openapi(), indent=2) )" > $@

	# validates OAS file: $@
	$(call validate_openapi_specs,$@)

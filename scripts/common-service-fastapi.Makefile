#
# Extends service makefile with recipes specific to fastapi-based apps
#

.env: ## local service envfile (used mostly for local development)
	cp .env-devel $@

.PHONY: openapi-specs openapi.json
openapi-specs: openapi.json
openapi.json: .env ## OpenApi Specification (OAS) file
	# generating openapi specs file
	python3 -c "import json; from $(APP_PACKAGE_NAME).main import *; print( json.dumps(the_app.openapi(), indent=2) )" > $@
	# validates OAS file: $@
	@cd $(CURDIR); \
	$(SCRIPTS_DIR)/openapi-generator-cli.bash validate --input-spec /local/$@

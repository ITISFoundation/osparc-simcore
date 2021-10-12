#
# Extends service makefile with recipes specific to fastapi-based apps
#

.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)


.PHONY: openapi-specs openapi.json
openapi-specs: openapi.json
openapi.json: .env ## OpenApi Specification (OAS) file
	# generating openapi specs file
	@set -o allexport; \
	source .env; \
	set +o allexport; \
	python3 -c "import json; from $(APP_PACKAGE_NAME).main import *; print( json.dumps(the_app.openapi(), indent=2) )" > $@
	# validates OAS file: $@
	@cd $(CURDIR); \
	$(SCRIPTS_DIR)/openapi-generator-cli.bash validate --input-spec /local/$@

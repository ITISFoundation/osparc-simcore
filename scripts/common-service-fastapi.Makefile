#
# Extends service makefile with recipes specific to fastapi-based apps
#

.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)


.PHONY: openapi-specs openapi.json openapi.yaml

#
# NOTE that the scripts below assume that the package will have a main.py
#      with 'the_app':FastAPI global defined inside  (provided by the cookiecutter)
#

openapi.json: .env
	# generating openapi specs in a JSON file
	@set -o allexport; \
	source .env; \
	set +o allexport; \
	python3 -c "import json; from $(APP_PACKAGE_NAME).main import *; print( json.dumps(the_app.openapi(), indent=2) )" > $@
	# validates OAS file: $@
	@cd $(CURDIR); \
	$(SCRIPTS_DIR)/openapi-generator-cli.bash validate --input-spec /local/$@

openapi.yaml: .env
	# generating openapi specs in a YAML file
	@set -o allexport; \
	source .env; \
	set +o allexport; \
	python3 -c "import yaml; import sys; from $(APP_PACKAGE_NAME).main import *; print( yaml.safe_dump(the_app.openapi(), sys.stdout, indent=2, sort_keys=False) )" > $@


openapi-specs: openapi.json openapi.yaml ## OpenApi Specification (OAS) file

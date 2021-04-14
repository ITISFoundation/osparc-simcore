include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

APP_NAME := $(notdir $(CURDIR))

.DEFAULT_GOAL := help


.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)


.PHONY: openapi.json
openapi.json: .env ## Creates OAS document openapi.json
	# generating openapi specs (OAS) file
	export $(shell grep -v '^#' $< | xargs -0) && python3 -c "import json; from $(APP_PACKAGE_NAME).main import *; print( json.dumps(app.openapi(), indent=2) )" > $@
	# validates OAS file: $@
	@cd $(CURDIR); \
	$(SCRIPTS_DIR)/openapi-generator-cli.bash validate --input-spec /local/$@


.PHONY: codestyle
codestyle: ## enforces codestyle and runs pylint and mypy
	isort setup.py src/simcore_service_dynamic_sidecar tests
	black src/simcore_service_dynamic_sidecar tests/
	pylint --rcfile=../../.pylintrc src/simcore_service_dynamic_sidecar tests/
	mypy src/simcore_service_dynamic_sidecar tests/ --ignore-missing-imports


.PHONY: run-github-action-locally
run-github-action-locally:  ## runs "unit-test-dynamic-sidecar" defined int github workflow locally
	# Note: ⚡ act is required https://github.com/nektos/act to emulate the github actons locally
	@act -C ../../. -P ubuntu-20.04=catthehacker/ubuntu:act-20.04 -j unit-test-dynamic-sidecar

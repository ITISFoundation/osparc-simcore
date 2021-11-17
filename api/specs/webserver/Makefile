include ../../../scripts/common.Makefile

PY_SCRIPTS = $(wildcard scripts/*.py)

openapi-v1.ignore.yml: $(PY_SCRIPTS)
	# generating OAS file: $(CURDIR)/$@
	python scripts/create-openapi.py > $@
	# validating OAS file: $(CURDIR)/$@
	$(SCRIPTS_DIR)/openapi-generator-cli.bash validate --input-spec /local/$@

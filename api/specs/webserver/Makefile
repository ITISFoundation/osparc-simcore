include ../../../scripts/common.Makefile
# FIXME: base version-* targets do not apply here

PY_SCRIPTS = $(wildcard scripts/*.py)


.PHONY: openapi-v1.ignore.yml openapi
openapi: openapi-v1.ignore.yml ## creates OAS using scripts
openapi-v1.ignore.yml: $(PY_SCRIPTS)
	# generating OAS file: $(CURDIR)/$@
	python scripts/create-openapi.py > $@
	# validating OAS file: $(CURDIR)/$@
	$(SCRIPTS_DIR)/openapi-generator-cli.bash validate --input-spec /local/$@

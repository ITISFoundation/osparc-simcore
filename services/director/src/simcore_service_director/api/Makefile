.DEFAULT_GOAL := openapi-specs


API_MAJOR_VERSION = $(shell echo 0.1.0 | cut -f1 -d.)
API_SPECS_DIR  = $(CURDIR)/v${API_MAJOR_VERSION}
API_SHARED_DIR = $(abspath $(CURDIR)../../../../../../api/specs/shared)
OAS_SOURCES    = $(shell find ${API_SPECS_DIR}/oas-parts -type f -name '*.y*ml')
OAS_TARGET     = $(API_SPECS_DIR)/openapi.yaml



.PHONY: .update-schemas
.update-schemas:
	# Updating common schemas
	@$(MAKE) -C ${API_SHARED_DIR}/schemas
	# Updating schemas
	# @$(MAKE) -C ${API_SPECS_DIR}/schemas


${OAS_TARGET}: ${OAS_SOURCES} .update-schemas
	# bundling '${API_SPECS_DIR}' to '${OAS_TARGET}' ...
	@swagger-cli bundle -o $@ -t yaml -r "${API_SPECS_DIR}/openapi.yaml"


.PHONY: openapi-specs
openapi-specs: ${OAS_TARGET} ## creates and validates OpenAPI specs
	# Validating bundled '${OAS_TARGET}'
	@swagger-cli validate $<

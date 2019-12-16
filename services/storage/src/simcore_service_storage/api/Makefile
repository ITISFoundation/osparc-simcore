.DEFAULT_GOAL := openapi-specs


API_MAJOR_VERSION = $(shell echo 0.1.0 | cut -f1 -d.)
API_SPECS_DIR = $(CURDIR)/v${API_MAJOR_VERSION}
API_PARTS_DIR = ${API_SPECS_DIR}/oas-parts
API_SHARED_DIR = $(abspath $(CURDIR)../../../../../../api/specs/shared)
OAS_SOURCES   = $(shell find ${API_PARTS_DIR} -type f -name '*.y*ml')
OAS_TARGET    = $(API_SPECS_DIR)/openapi.yaml



.PHONY: .update-schemas
.update-schemas:
	# Updating common schemas
	@$(MAKE) -C ${API_SHARED_DIR}/schemas
	# Updating schemas
	@$(MAKE) -C ${API_PARTS_DIR}/components/schemas


${OAS_TARGET}: ${OAS_SOURCES} #.update-schemas
	# bundling '${API_SPECS_DIR}' to '${OAS_TARGET}' ...
	@swagger-cli bundle --outfile $@ --type yaml --dereference $ ${API_PARTS_DIR}/openapi.yaml


.PHONY: openapi-specs
openapi-specs: ${OAS_TARGET} ## creates and validates OpenAPI specs
	# Validating bundled '${OAS_TARGET}'
	@swagger-cli validate $<

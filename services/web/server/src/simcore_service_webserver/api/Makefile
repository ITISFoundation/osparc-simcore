.DEFAULT_GOAL := openapi-specs

API_SHARED_DIR = $(abspath $(CURDIR)../../../../../../../api/specs/shared)

APP_DIR = $(abspath $(CURDIR)../../../../)

API_MAJOR_VERSION = $(shell cat ${APP_DIR}/VERSION | cut -f1 -d.)
API_SPECS_DIR = $(CURDIR)/v${API_MAJOR_VERSION}
API_PARTS_DIR = ${API_SPECS_DIR}/oas-parts

OAS_SOURCES   = $(shell find ${API_PARTS_DIR} -type f -name '*.y*ml')
OAS_TARGET    = $(API_SPECS_DIR)/openapi.yaml

API_SHARED_JSON_SCHEMAS = $(shell find ${API_SHARED_DIR}/schemas -type f -name '*.json')

WEB_CLIENT_DIR = $(abspath $(APP_DIR)/../client)


.PHONY: .update-schemas
.update-schemas:
	# Updating common schemas
	@$(MAKE) -C ${API_SHARED_DIR}/schemas
	# Updating ${API_SPECS_DIR}/schemas with common json-schemas
	@cp --target-directory=${API_SPECS_DIR}/schemas \
		--verbose \
		--update  \
		${API_SHARED_JSON_SCHEMAS}



${OAS_TARGET}: ${OAS_SOURCES} .update-schemas
	# bundling '${API_SPECS_DIR}' to '${OAS_TARGET}' ...
	@swagger-cli bundle --dereference --outfile $@ --type yaml  ${API_PARTS_DIR}/openapi.yaml


.PHONY: openapi-specs
openapi-specs: ${OAS_TARGET} ## creates and validates OpenAPI specs
	# Validating bundled '${OAS_TARGET}'
	@swagger-cli validate $<
	# Copies specs as client resources
	@cp -vp $< -t ${WEB_CLIENT_DIR}/source/resource/api

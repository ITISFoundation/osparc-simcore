.DEFAULT_GOAL := openapi-specs

APP_DIR  := $(abspath $(CURDIR)../../../../)
APP_NAME := webserver

API_MAJOR_VERSION := $(shell cat ${APP_DIR}/VERSION | cut -f1 -d.)
APP_API_DIR       := $(CURDIR)/v${API_MAJOR_VERSION}
OAS_TARGET        := ${APP_API_DIR}/openapi.yaml

API_SPECS_DIR = $(abspath $(CURDIR)../../../../../../../api/specs)
API_PARTS_DIR = ${API_SPECS_DIR}/${APP_NAME}
OAS_SOURCES   = $(shell find  ${API_PARTS_DIR} -type f -name '*.y*ml')

API_COMMON_JSON_SCHEMAS = $(shell find ${API_SPECS_DIR}/common/schemas -type f -name '*.json')

WEB_CLIENT_DIR = $(abspath $(APP_DIR)/../client)


.PHONY: .update-schemas
.update-schemas:
	# Convert common schemas to openapi-compatible schemas
	@$(MAKE) --directory ${API_SPECS_DIR}/common/schemas
	# Updating ${API_SPECS_DIR}/schemas with common json-schemas
	@cp --target-directory=${APP_API_DIR}/schemas \
		--verbose \
		--remove-destination \
		${API_COMMON_JSON_SCHEMAS}


${OAS_TARGET}: ${OAS_SOURCES} .update-schemas
	# bundling '${API_SPECS_DIR}/${APP_NAME}' to '${OAS_TARGET}' ...
	@swagger-cli bundle \
		--dereference \
		--outfile $@ \
		--type yaml  \
		"${API_SPECS_DIR}/${APP_NAME}/openapi.yaml"


.PHONY: openapi-specs
openapi-specs: ${OAS_TARGET} ## creates and validates OpenAPI specs
	# Validating bundled '${OAS_TARGET}'
	@swagger-cli validate $<
	# Copies specs as client resources
	@cp -v --preserve $< -t ${WEB_CLIENT_DIR}/source/resource/api

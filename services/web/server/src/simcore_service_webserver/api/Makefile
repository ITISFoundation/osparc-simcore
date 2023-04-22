.DEFAULT_GOAL := openapi-specs

APP_DIR  := $(abspath $(CURDIR)../../../../)
APP_NAME := webserver

API_MAJOR_VERSION := $(shell cat ${APP_DIR}/VERSION | cut -f1 -d.)
APP_API_DIR       := $(CURDIR)/v${API_MAJOR_VERSION}
OAS_TARGET        := ${APP_API_DIR}/openapi.yaml

API_SPECS_DIR = $(abspath $(CURDIR)../../../../../../../api/specs)
API_PARTS_DIR = ${API_SPECS_DIR}/${APP_NAME}
OAS_SOURCES   = $(shell find  ${API_PARTS_DIR} -type f -name '*.y*ml')



${OAS_TARGET}: ${OAS_SOURCES}
	# bundling '${API_SPECS_DIR}/${APP_NAME}' to '${OAS_TARGET}' ...
	@swagger-cli bundle \
		--outfile $@ \
		--type yaml  \
		"${API_SPECS_DIR}/${APP_NAME}/openapi.yaml"


.PHONY: openapi-specs
openapi-specs: ${OAS_TARGET} ## creates and validates OpenAPI specs
	# Validating bundled '${OAS_TARGET}'
	swagger-cli validate $<

#
# TODO: under development
#
.DEFAULT_GOAL := openapi-specs

API_VERSION   := v0
API_SPECS_DIR := $(CURDIR)/${API_VERSION}
OAS_SOURCES   := $(shell find ${API_SPECS_DIR}/ -type f -name '*.y*ml')
OAS_TARGET    := openapi-${API_VERSION}.yaml


# TODO: container with https://www.npmjs.com/package/swagger-cli
${OAS_TARGET}: $(OAS_SOURCES)
	# bundling '${API_SPECS_DIR}' to '${OAS_TARGET}' ...
	swagger-cli bundle -o $@ -t yaml -r "${API_SPECS_DIR}/openapi.yaml"


.PHONY: openapi-specs
openapi-specs: ${OAS_TARGET} ## creates and validates OpenAPI specs
	# Validating bundled '${OAS_TARGET}'
	swagger-cli validate $<

#
# Targets for DEVELOPMENT of Components Catalog Service
#
.DEFAULT_GOAL := help

include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/service.mk



.PHONY: openapi-specs openapi.json
openapi-specs: openapi.json
openapi.json: .env-ignore
	$(call generate_and_validate_openapi,$<,$@)

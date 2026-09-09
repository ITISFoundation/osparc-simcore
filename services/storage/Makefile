#
# Targets for DEVELOPMENT for Storage service
#
.DEFAULT_GOAL := help

include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/service.mk


.PHONY: openapi.json
openapi-specs: openapi.json
openapi.json: .env
	$(call generate_and_validate_openapi,$<,$@)

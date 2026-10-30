#
# DEVELOPMENT recipes for notifications
#
.DEFAULT_GOAL := help

include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/service.mk


.PHONY: openapi.json
openapi-specs: openapi.json
openapi.json: .env-ignore ## produces openapi.json
	$(call generate_and_validate_openapi,$<,$@)

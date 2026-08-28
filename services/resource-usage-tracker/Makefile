#
# DEVELOPMENT recipes for resource-usage-tracker
#
.DEFAULT_GOAL := help

include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/service.mk



.PHONY: openapi.json
openapi-specs: openapi.json
openapi.json:  ## produces openapi.json
	$(call generate_and_validate_openapi,,$@)

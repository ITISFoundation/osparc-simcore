#
# DEVELOPMENT recipes for dynamic-scheduler
#
.DEFAULT_GOAL := help

include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/service.mk


.PHONY: openapi.json
openapi-specs: openapi.json
openapi.json: .env-ignore ## produces openapi.json
	$(call generate_and_validate_openapi,$<,$@)

.PHONY: workflows_signatures.json
workflows_signatures.json: ## produces workflows_signatures.json
	$(APP_CLI_NAME) workflows-signatures > $@

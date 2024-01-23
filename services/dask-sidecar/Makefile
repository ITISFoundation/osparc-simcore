#
# DEVELOPMENT recipes for Workflows manager service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile


TEMP_DIR := $(shell mktemp -d -t dask-docker-XXX)

.PHONY: settings-schema.json
settings-schema.json: ## [container] dumps json-shcema of this service settings
	# Dumping settings schema of ${DOCKER_REGISTRY}/${APP_NAME}:${DOCKER_IMAGE_TAG}
	@docker run \
		--entrypoint="${APP_CLI_NAME}" \
		${DOCKER_REGISTRY}/${APP_NAME}:${DOCKER_IMAGE_TAG} \
		settings --as-json-schema \
		| sed --expression='1,/{/ {/{/!d}' \
		> $@
	# Dumped '$(CURDIR)/$@'

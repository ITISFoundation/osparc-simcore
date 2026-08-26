#
# DEVELOPMENT recipes for invitations
#
.DEFAULT_GOAL := help

include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/service.mk



ENV_IGNORE_FLAGS := --auto-password

.PHONY: openapi.json
openapi-specs: openapi.json
openapi.json: .env-ignore ## produces openapi.json
	$(call generate_and_validate_openapi,$<,$@)


#
# docker container
#

DOCKER_REGISTRY ?=local
DOCKER_IMAGE_TAG ?=production
DOCKER_IMAGE_NAME :=$(DOCKER_REGISTRY)/$(APP_NAME):$(DOCKER_IMAGE_TAG)

.PHONY: run
run: .env build ## [docker] runs in container
	docker run --interactive --tty \
	--env-file .env \
	--publish 8000:8000 \
	$(DOCKER_IMAGE_NAME) \
	$(APP_CLI_NAME) serve

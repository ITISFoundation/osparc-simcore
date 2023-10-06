#
# DEVELOPMENT recipes for invitations
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile



.env-ignore:
	$(APP_CLI_NAME) generate-dotenv --auto-password > $@


.PHONY: openapi.json
openapi-specs: openapi.json
openapi.json: .env-ignore ## produces openapi.json
	# generating openapi specs file (need to have the environment set for this)
	@set -o allexport; \
	source $<; \
	set +o allexport; \
	python3 -c "import json; from $(APP_PACKAGE_NAME).web_main import *; print( json.dumps(the_app.openapi(), indent=2) )" > $@


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

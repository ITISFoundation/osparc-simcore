DOCKER_REGISTRY ?= itisfoundation
DOCKER_IMAGE_NAME ?= puppeteer
DOCKER_IMAGE_TAG ?= latest


.PHONY: help

help: ## help on rule's targets
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build build-kit build-x: ## builds a node image able to run puppeteer
	@$(if $(findstring -kit,$@),export DOCKER_BUILDKIT=1;export COMPOSE_DOCKER_CLI_BUILD=1;,) \
	$(if $(findstring -x,$@),\
		docker buildx build --tag $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) .;,\
		docker build --tag $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) .;\
	)

shell: ## runs bash in the image to allow manual testing
	@docker run -it $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) bash

push: ## publish the image
	# pushing $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG)...
	@docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG)

guard-%:
	@if [ "${${*}}" = "" ]; then echo "Environment variable $* not set"; exit 1; fi


OSPARC_ROOT_DIR := $(realpath $(CURDIR)/../../../)

test-local: guard-URL guard-USER guard-PASSWORD ## test e2e sleepers scenario by using local osparc-simcore and running the sleepers tutorial (needs URL, USER and PASSWORD)
	@docker run --volume $(OSPARC_ROOT_DIR)/tests/e2e:/osparc-simcore/tests/e2e -it $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) "npm i /osparc-simcore/tests/e2e/; node /osparc-simcore/tests/e2e/tutorials/sleepers.js $(URL) $(USER) $(PASSWORD)"


test-ci: guard-URL guard-USER guard-PASSWORD ## test e2e sleepers scenario by clone osparc-simcore and running the sleepers tutorial (needs URL, USER and PASSWORD)
	@docker run -it $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) "git clone https://github.com/ITISFoundation/osparc-simcore.git; npm i osparc-simcore/tests/e2e/; node osparc-simcore/tests/e2e/tutorials/sleepers.js $(URL) $(USER) $(PASSWORD)"

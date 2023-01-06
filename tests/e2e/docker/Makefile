DOCKER_REGISTRY ?= itisfoundation
DOCKER_IMAGE_NAME ?= puppeteer
# $(puppeteer-version)-$(our-version)
DOCKER_IMAGE_TAG ?= 14-3

# version control
VCS_URL          := $(shell git config --get remote.origin.url)
VCS_REF          := $(shell git rev-parse --short HEAD)
BUILD_DATE       := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

.PHONY: help
help: ## help on rule's targets
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: build
build: ## builds a node image able to run puppeteer
	docker buildx build --build-arg BUILD_DATE=$(BUILD_DATE) --build-arg VCS_URL=$(VCS_URL) --build-arg VCS_REF=$(VCS_REF) --tag $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) .;

.PHONY: shell
shell:  guard-URL guard-USER guard-PASSWORD ## runs bash in the image to allow manual testing
	@docker run --env URL=$(URL) --env USER=$(USER) --env PASSWORD=$(PASSWORD) -it $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) bash

.PHONY: push
push: ## publish the image
	# pushing $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG)...
	@docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG)

.PHONY: guard-%
guard-%:
	@if [ "${${*}}" = "" ]; then echo "Environment variable $* not set"; exit 1; fi


OSPARC_ROOT_DIR := $(realpath $(CURDIR)/../../../)
.PHONY: test-local
test-local: guard-URL guard-USER guard-PASSWORD ## test e2e sleepers scenario by using local osparc-simcore and running the sleepers tutorial (needs URL, USER and PASSWORD)
	@docker run --volume $(OSPARC_ROOT_DIR)/tests/e2e:/osparc-simcore/tests/e2e -it $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) bash -c "npm i /osparc-simcore/tests/e2e/; node /osparc-simcore/tests/e2e/tutorials/sleepers.js $(URL) --user $(USER) --pass $(PASSWORD)"

.PHONY: test-ci
test-ci test-ci-staging test-ci-release: guard-URL guard-USER guard-PASSWORD ## test e2e sleepers scenario by clone osparc-simcore and running the sleepers tutorial (needs URL, USER and PASSWORD)
	@docker run -it $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) bash -c \
		"git clone https://github.com/ITISFoundation/osparc-simcore.git; \
		$(if $(or $(findstring -staging,$@), $(findstring -release,$@)),\
		pushd osparc-simcore; \
		git checkout $$(git describe --match="$(if $(findstring -staging,$@),staging_*,v*)" --tags --abbrev=0); \
		popd; \
		,) \
		npm i osparc-simcore/tests/e2e/; \
		node osparc-simcore/tests/e2e/tutorials/sleepers.js $(URL) --user $(USER) --pass $(PASSWORD)"

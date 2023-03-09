#
# DEVELOPMENT recipes for Workflows manager service
#
include ../../../scripts/common.Makefile
include ../../../scripts/common-package.Makefile


PACKAGE_NAME=osparc_gateway_server
COVERAGERC_PATH=../../../.coveragerc
# version tags
export DOCKER_IMAGE_TAG ?= latest
export DOCKER_REGISTRY  ?= itisfoundation

.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt

.PHONY: tests-unit tests-unit-ci tests-integration tests-integration-ci tests
tests-unit: ## runs unit tests
	# running unit tests
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=$(COVERAGERC_PATH) \
		--cov-report=term-missing \
		--cov=$(PACKAGE_NAME) \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--keep-docker-up \
		--pdb \
		-vv \
		$(CURDIR)/tests/unit

tests-unit-ci: ## runs unit tests with ci parameters
	# running unit tests
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-append \
		--cov-config=$(COVERAGERC_PATH) \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=$(PACKAGE_NAME) \
		--durations=10 \
		--keep-docker-up \
		--log-date-format="%Y-%m-%d %H:%M:%S" \
    --log-format="%(asctime)s %(levelname)s %(message)s" \
		--verbose \
		-m "not heavy_load" \
		$(CURDIR)/tests/unit

tests-integration: ## runs integration tests against local+production images
	# running integration tests local/(service):production images ...
	@export DOCKER_REGISTRY=local; \
	export DOCKER_IMAGE_TAG=production; \
	pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=$(COVERAGERC_PATH) \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=$(PACKAGE_NAME) \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--keep-docker-up \
		--pdb \
		--verbose \
		$(CURDIR)/tests/integration

tests-integration-ci: ## runs integration tests against local+production images with CI parameters
	pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-append \
		--cov-config=$(COVERAGERC_PATH) \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=$(PACKAGE_NAME) \
		--durations=10 \
		--keep-docker-up \
		--log-date-format="%Y-%m-%d %H:%M:%S" \
		--verbose \
		-m "not heavy_load" \
		--log-format="%(asctime)s %(levelname)s %(message)s" \
		$(CURDIR)/tests/integration

tests: tests-unit tests-integration ## runs all tests
	# running tests


##
## BUILD
##
SERVICES_LIST := osparc-gateway-server

.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)



# version control
export VCS_URL          := $(shell git config --get remote.origin.url)
export VCS_REF          := $(shell git rev-parse --short HEAD)
export VCS_STATUS_CLIENT:= $(if $(shell git status -s),'modified/untracked','clean')
export BUILD_DATE       := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
# docker buildx cache location
DOCKER_BUILDX_CACHE_FROM ?= /tmp/.buildx-cache
DOCKER_BUILDX_CACHE_TO ?= /tmp/.buildx-cache
DOCKER_TARGET_PLATFORMS ?= linux/amd64
comma := ,

define _docker_compose_build
$(if $(create_cache),$(info creating cache file in $(DOCKER_BUILDX_CACHE_TO)),)
export BUILD_TARGET=$(if $(findstring -devel,$@),development,production) && \
$(foreach service, $(SERVICES_LIST),\
	$(if $(push),\
		export $(subst -,_,$(shell echo $(service) | tr a-z A-Z))_VERSION=$(shell cat services/$(service)/VERSION);\
	,) \
)\
docker buildx bake \
	$(if $(findstring -devel,$@),,\
	--set *.platform=$(DOCKER_TARGET_PLATFORMS) \
	$(foreach service, $(SERVICES_LIST),\
		--set $(service).cache-from="type=local,src=$(DOCKER_BUILDX_CACHE_FROM)/$(service)" \
		$(if $(create_cache),--set $(service).cache-to="type=local$(comma)mode=max$(comma)dest=$(DOCKER_BUILDX_CACHE_TO)/$(service)",) \
	)\
	)\
	$(if $(findstring $(comma),$(DOCKER_TARGET_PLATFORMS)),,--set *.output="type=docker$(comma)push=false") \
	$(if $(push),--push,) \
	$(if $(push),--file docker-bake.hcl,) --file docker-compose-build.yml $(if $(target),$(target),)
endef

.PHONY: build build-nc rebuild build-devel build-devel-nc
rebuild: build-nc # alias
build build-nc: .env ## Builds production images and tags them as 'local/{service-name}:production'. For single target e.g. 'make target=osparc-$(SWARM_STACK_NAME) build'
ifeq ($(target),)
	# Building services
	@$(_docker_compose_build)
else
	# Building service $(target)
	@$(_docker_compose_build)
endif


build-devel build-devel-nc: .env ## Builds development images and tags them as 'local/{service-name}:development'. For single target e.g. 'make target=osparc-$(SWARM_STACK_NAME) build-devel'
ifeq ($(target),)
	# Building services
	@$(_docker_compose_build)
else
	# Building service $(target)
	@@$(_docker_compose_build)
endif

##
## TAGGING
##
.PHONY: tag-local tag-version tag-latest
tag-local: ## Tags version '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}' images as 'local/{service}:production'
	# Tagging all '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}' as 'local/{service}:production'
	@$(foreach service, $(SERVICES_LIST)\
		,docker tag ${DOCKER_REGISTRY}/$(service):${DOCKER_IMAGE_TAG} local/$(service):production; \
	)

tag-version: ## Tags 'local/{service}:production' images as versioned '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}'
	# Tagging all 'local/{service}:production' as '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}'
	@$(foreach service, $(SERVICES_LIST)\
		,docker tag local/$(service):production ${DOCKER_REGISTRY}/$(service):${DOCKER_IMAGE_TAG}; \
	)

tag-latest: ## Tags last locally built production images as '${DOCKER_REGISTRY}/{service}:latest'
	@export DOCKER_IMAGE_TAG=latest; \
	$(MAKE) tag-version

##
## INFOS
##
.PHONY: info-images info-swarm  info-tools
define show-meta
	$(foreach iid,$(shell docker images "*/$(1):*" -q | sort | uniq),\
		docker image inspect $(iid) | jq '.[0] | .RepoTags, .Config.Labels, .Architecture';)
endef

info-images:  ## lists tags and labels of built images. To display one: 'make target=webserver info-images'
ifeq ($(target),)
	@$(foreach service,$(SERVICES_LIST),\
		echo "## $(service) images:";\
			docker images */$(service):*;\
			$(call show-meta,$(service))\
		)
else
	## $(target) images:
	@$(call show-meta,$(target))
endif

info-swarm: ## displays info about stacks and networks
ifneq ($(SWARM_HOSTS), )
	# Stacks in swarm
	@docker stack ls
	# Containers (tasks) running in '$(SWARM_STACK_NAME)' stack
	-@docker stack ps $(SWARM_STACK_NAME)
	# Services in '$(SWARM_STACK_NAME)' stack
	-@docker stack services $(SWARM_STACK_NAME)
	# Networks
	@docker network ls
endif

## Initial config
.PHONY: config
# osparc-dask-gateway configuration file
export OSPARC_GATEWAY_CONFIG_FILE_HOST = .osparc-dask-gateway-config.py
$(OSPARC_GATEWAY_CONFIG_FILE_HOST): $(CURDIR)/config/default_config.py  ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)
config: $(OSPARC_GATEWAY_CONFIG_FILE_HOST)  ## create default configuration file

# osparc-simcore general makefile
#
# NOTES:
# 	- GNU make version 4.2 recommended
# 	- Use 'make -n *' to dry-run during debugging
# 	- In windows, only WSL is supported
#
# by sanderegg, pcrespov
#
.DEFAULT_GOAL := help

SHELL := /bin/bash


MAKE_C := $(MAKE) --no-print-directory --directory

# Operating system
ifeq ($(filter Windows_NT,$(OS)),)
IS_WSL  := $(if $(findstring Microsoft,$(shell uname -a)),WSL,)
IS_OSX  := $(filter Darwin,$(shell uname -a))
IS_LINUX:= $(if $(or $(IS_WSL),$(IS_OSX)),,$(filter Linux,$(shell uname -a)))
endif

IS_WIN  := $(strip $(if $(or $(IS_LINUX),$(IS_OSX),$(IS_WSL)),,$(OS)))
$(if $(IS_WIN),$(error Windows is not supported in all recipes. Use WSL instead. Follow instructions in README.md),)


# VARIABLES ----------------------------------------------
# TODO: read from docker-compose file instead $(shell find  $(CURDIR)/services -type f -name 'Dockerfile')
# or $(notdir $(subst /Dockerfile,,$(wildcard services/*/Dockerfile))) ...
SERVICES_LIST := \
	api-server \
	catalog \
	director \
	migration \
	sidecar \
	storage \
	webserver

CLIENT_WEB_OUTPUT       := $(CURDIR)/services/web/client/source-output

# version control
export VCS_URL          := $(shell git config --get remote.origin.url)
export VCS_REF          := $(shell git rev-parse --short HEAD)
export VCS_REF_CLIENT   := $(shell git log --pretty=tformat:"%h" -n1 services/web/client)
export VCS_STATUS_CLIENT:= $(if $(shell git status -s),'modified/untracked','clean')
export BUILD_DATE       := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

# api-versions
export API_SERVER_API_VERSION := $(shell cat $(CURDIR)/services/api-server/VERSION)
export CATALOG_API_VERSION    := $(shell cat $(CURDIR)/services/catalog/VERSION)
export DIRECTOR_API_VERSION   := $(shell cat $(CURDIR)/services/director/VERSION)
export STORAGE_API_VERSION    := $(shell cat $(CURDIR)/services/storage/VERSION)
export WEBSERVER_API_VERSION  := $(shell cat $(CURDIR)/services/web/server/VERSION)


# swarm stacks
export SWARM_STACK_NAME ?= master-simcore
export SWARM_STACK_NAME_NO_HYPHEN = $(subst -,_,$(SWARM_STACK_NAME))

# version tags
export DOCKER_IMAGE_TAG ?= latest
export DOCKER_REGISTRY  ?= itisfoundation


.PHONY: help

help: ## help on rule's targets
ifeq ($(IS_WIN),)
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
else
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
endif



## DOCKER BUILD -------------------------------
#
# - all builds are inmediatly tagged as 'local/{service}:${BUILD_TARGET}' where BUILD_TARGET='development', 'production', 'cache'
# - only production and cache images are released (i.e. tagged pushed into registry)
#
SWARM_HOSTS = $(shell docker node ls --format="{{.Hostname}}" 2>$(if $(IS_WIN),NUL,/dev/null))

.PHONY: build build-nc rebuild build-devel build-devel-nc build-devel-kit build-devel-x build-cache build-cache-kit build-cache-x build-cache-nc build-kit build-x

define _docker_compose_build
export BUILD_TARGET=$(if $(findstring -devel,$@),development,$(if $(findstring -cache,$@),cache,production));\
$(if $(findstring -x,$@),\
	pushd services; docker buildx bake --file docker-compose-build.yml; popd;,\
	docker-compose -f services/docker-compose-build.yml build $(if $(findstring -nc,$@),--no-cache,) $(if $(target),,--parallel)\
)
endef

rebuild: build-nc # alias
build build-nc build-kit build-x: .env ## Builds production images and tags them as 'local/{service-name}:production'. For single target e.g. 'make target=webserver build'
ifeq ($(target),)
	# Compiling front-end

	@$(if $(findstring -kit,$@),export DOCKER_BUILDKIT=1;export COMPOSE_DOCKER_CLI_BUILD=1;,) \
	$(MAKE_C) services/web/client compile$(if $(findstring -x,$@),-x,)

	# Building services
	@$(if $(findstring -kit,$@),export DOCKER_BUILDKIT=1;export COMPOSE_DOCKER_CLI_BUILD=1;,) \
	$(_docker_compose_build)
else
ifeq ($(findstring webserver,$(target)),webserver)
	# Compiling front-end
	@$(if $(findstring -kit,$@),export DOCKER_BUILDKIT=1;export COMPOSE_DOCKER_CLI_BUILD=1;,) \
	$(MAKE_C) services/web/client clean compile$(if $(findstring -x,$@),-x,)
endif
	# Building service $(target)
	@$(if $(findstring -kit,$@),export DOCKER_BUILDKIT=1;export COMPOSE_DOCKER_CLI_BUILD=1;,) \
	$(_docker_compose_build) $(target)
endif


build-devel build-devel-nc build-devel-kit build-devel-x: .env ## Builds development images and tags them as 'local/{service-name}:development'. For single target e.g. 'make target=webserver build-devel'
ifeq ($(target),)
	# Building services
	@$(if $(findstring -kit,$@),export DOCKER_BUILDKIT=1;export COMPOSE_DOCKER_CLI_BUILD=1;,) \
	$(_docker_compose_build)
else
ifeq ($(findstring webserver,$(target)),webserver)
	# Compiling front-end
	@$(if $(findstring -kit,$@),export DOCKER_BUILDKIT=1;export COMPOSE_DOCKER_CLI_BUILD=1;,) \
	$(MAKE_C) services/web/client touch$(if $(findstring -x,$@),-x,) compile-dev
endif
	# Building service $(target)
	@$(if $(findstring -kit,$@),export DOCKER_BUILDKIT=1;export COMPOSE_DOCKER_CLI_BUILD=1;,) \
	$(_docker_compose_build) $(target)
endif


build-cache build-cache-nc build-cache-kit build-cache-x: .env ## Build cache images and tags them as 'local/{service-name}:cache'
ifeq ($(target),)
	# Compiling front-end
	@$(if $(findstring -kit,$@),export DOCKER_BUILDKIT=1;export COMPOSE_DOCKER_CLI_BUILD=1;,)
	$(MAKE_C) services/web/client compile$(if $(findstring -x,$@),-x,)
	# Building cache images
	@$(if $(findstring -kit,$@),export DOCKER_BUILDKIT=1;export COMPOSE_DOCKER_CLI_BUILD=1;,)
	$(_docker_compose_build)
else
	@$(if $(findstring -kit,$@),export DOCKER_BUILDKIT=1;export COMPOSE_DOCKER_CLI_BUILD=1;,)
	$(_docker_compose_build) $(target)
endif


$(CLIENT_WEB_OUTPUT):
	# Ensures source-output folder always exists to avoid issues when mounting webclient->webserver dockers. Supports PowerShell
	-mkdir $(if $(IS_WIN),,-p) $(CLIENT_WEB_OUTPUT)


.PHONY: shell
shell:
	docker run -it local/$(target):production /bin/sh


## DOCKER SWARM -------------------------------
#
# - All resolved configuration are named as .stack-${name}-*.yml to distinguish from docker-compose files which can be parametrized
#
SWARM_HOSTS            = $(shell docker node ls --format="{{.Hostname}}" 2>$(if $(IS_WIN),null,/dev/null))
docker-compose-configs = $(wildcard services/docker-compose*.yml)
CPU_COUNT = $(shell cat /proc/cpuinfo | grep processor | wc -l )

.stack-simcore-development.yml: .env $(docker-compose-configs)
	# Creating config for stack with 'local/{service}:development' to $@
	@export DOCKER_REGISTRY=local \
	export DOCKER_IMAGE_TAG=development; \
	export DEV_PC_CPU_COUNT=${CPU_COUNT}; \
	docker-compose -f services/docker-compose.yml -f services/docker-compose.local.yml -f services/docker-compose.devel.yml --log-level=ERROR config > $@

.stack-simcore-production.yml: .env $(docker-compose-configs)
	# Creating config for stack with 'local/{service}:production' to $@
	@export DOCKER_REGISTRY=local;       \
	export DOCKER_IMAGE_TAG=production; \
	docker-compose -f services/docker-compose.yml -f services/docker-compose.local.yml --log-level=ERROR config > $@

.stack-simcore-version.yml: .env $(docker-compose-configs)
	# Creating config for stack with '$(DOCKER_REGISTRY)/{service}:${DOCKER_IMAGE_TAG}' to $@
	@docker-compose -f services/docker-compose.yml -f services/docker-compose.local.yml --log-level=ERROR config > $@

.stack-ops.yml: .env $(docker-compose-configs)
	# Creating config for ops stack to $@
	@docker-compose -f services/docker-compose-ops.yml --log-level=ERROR config > $@


.PHONY: up-devel up-prod up-version up-latest .deploy-ops

.deploy-ops: .stack-ops.yml
	# Deploy stack 'ops'
ifndef ops_disabled
	@docker stack deploy -c $< ops
else
	@echo "Explicitly disabled with ops_disabled flag in CLI"
endif


up-devel: .stack-simcore-development.yml .init-swarm $(CLIENT_WEB_OUTPUT) ## Deploys local development stack, qx-compile+watch and ops stack (pass 'make ops_disabled=1 up-...' to disable)
	# Start compile+watch front-end container [front-end]
	$(MAKE_C) services/web/client down compile-dev flags=--watch
	# Deploy stack $(SWARM_STACK_NAME) [back-end]
	@docker stack deploy -c $< $(SWARM_STACK_NAME)
	$(MAKE) .deploy-ops
	$(MAKE_C) services/web/client follow-dev-logs


up-prod: .stack-simcore-production.yml .init-swarm ## Deploys local production stack and ops stack (pass 'make ops_disabled=1 up-...' to disable or target=<service-name> to deploy a single service)
ifeq ($(target),)
	# Deploy stack $(SWARM_STACK_NAME)
	@docker stack deploy -c $< $(SWARM_STACK_NAME)
	$(MAKE) .deploy-ops
else
	# deploys ONLY $(target) service
	docker-compose -f $< up --detach $(target)
endif

up-version: .stack-simcore-version.yml .init-swarm ## Deploys versioned stack '$(DOCKER_REGISTRY)/{service}:$(DOCKER_IMAGE_TAG)' and ops stack (pass 'make ops_disabled=1 up-...' to disable)
	# Deploy stack $(SWARM_STACK_NAME)
	@docker stack deploy -c $< $(SWARM_STACK_NAME)
	$(MAKE) .deploy-ops

up-latest:
	@export DOCKER_IMAGE_TAG=latest; \
	$(MAKE) up-version


.PHONY: down leave
down: ## Stops and removes stack
	# Removing stacks in reverse order to creation
	-$(foreach stack,\
		$(shell docker stack ls --format={{.Name}} | tac),\
		docker stack rm $(stack);)
	# Removing client containers (if any)
	-$(MAKE_C) services/web/client down
	# Removing generated docker compose configurations, i.e. .stack-*
	-$(shell rm $(wildcard .stack-*))
	# Removing local registry if any
	-$(shell docker rm --force $(local_registry))

leave: ## Forces to stop all services, networks, etc by the node leaving the swarm
	-docker swarm leave -f


.PHONY: .init-swarm
.init-swarm:
	# Ensures swarm is initialized
	$(if $(SWARM_HOSTS),,docker swarm init)


## DOCKER TAGS  -------------------------------

.PHONY: tag-local tag-cache tag-version tag-latest

tag-local: ## Tags version '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}' images as 'local/{service}:production'
	# Tagging all '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}' as 'local/{service}:production'
	@$(foreach service, $(SERVICES_LIST)\
		,docker tag ${DOCKER_REGISTRY}/$(service):${DOCKER_IMAGE_TAG} local/$(service):production; \
	)

tag-cache: ## Tags 'local/{service}:cache' images as '${DOCKER_REGISTRY}/{service}:cache'
	# Tagging all 'local/{service}:cache' as '${DOCKER_REGISTRY}/{service}:cache'
	@$(foreach service, $(SERVICES_LIST)\
		,docker tag local/$(service):cache ${DOCKER_REGISTRY}/$(service):cache; \
	)

tag-version: ## Tags 'local/{service}:production' images as versioned '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}'
	# Tagging all 'local/{service}:production' as '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}'
	@$(foreach service, $(SERVICES_LIST)\
		,docker tag local/$(service):production ${DOCKER_REGISTRY}/$(service):${DOCKER_IMAGE_TAG}; \
	)

tag-latest: ## Tags last locally built production images as '${DOCKER_REGISTRY}/{service}:latest'
	@export DOCKER_IMAGE_TAG=latest; \
	$(MAKE) tag-version



## DOCKER PULL/PUSH  -------------------------------
#
# TODO: cannot push modified/untracked
# TODO: cannot push disceted
#
.PHONY: pull-cache pull-version
pull-cache: .env
	@export DOCKER_IMAGE_TAG=cache; $(MAKE) pull-version

pull-version: .env ## pulls images from DOCKER_REGISTRY tagged as DOCKER_IMAGE_TAG
	# Pulling images '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}'
	@docker-compose -f services/docker-compose.yml pull


.PHONY: push-cache push-version push-latest

push-cache: tag-cache ## Pushes service images tagged as 'cache' into current registry
	@export DOCKER_IMAGE_TAG=cache; \
	$(MAKE) push-version

push-latest: tag-latest
	@export DOCKER_IMAGE_TAG=latest; \
	$(MAKE) push-version

# NOTE: docker-compose only pushes images with a 'build' section.
# TODO: change to docker-compose push when make config-version available
push-version: tag-version
	# pushing '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}'
	$(foreach service, $(SERVICES_LIST)\
		,docker push ${DOCKER_REGISTRY}/$(service):${DOCKER_IMAGE_TAG}; \
	)


## ENVIRONMENT -------------------------------

.PHONY: devenv devenv-all

.venv:
	python3 -m venv $@
	$@/bin/pip3 --quiet install --upgrade \
		pip \
		wheel \
		setuptools

devenv: .venv ## create a python virtual environment with dev tools (e.g. linters, etc)
	$</bin/pip3 --quiet install -r requirements.txt
	@echo "To activate the venv, execute 'source .venv/bin/activate'"

devenv-all: devenv ## sets up extra development tools (everything else besides python)
	# Upgrading client compiler
	@$(MAKE_C) services/web/client upgrade
	# Building tools
	@$(MAKE_C) scripts/json-schema-to-openapi-schema


.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)


.vscode/settings.json: .vscode-template/settings.json
	$(info WARNING: #####  $< is newer than $@ ####)
	@diff -uN $@ $<
	@false



## TOOLS -------------------------------

.PHONY: pylint

pylint: ## Runs python linter framework's wide
	/bin/bash -c "pylint --jobs=0 --rcfile=.pylintrc $(strip $(shell find services packages -iname '*.py' \
											-not -path "*egg*" \
											-not -path "*migration*" \
											-not -path "*datcore.py" \
											-not -path "*sandbox*" \
											-not -path "*-sdk/python*" \
											-not -path "*generated_code*" \
											-not -path "*datcore.py" \
											-not -path "*web/server*"))"
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes


.PHONY: new-service
new-service: .venv ## Bakes a new project from cookiecutter-simcore-pyservice and drops it under services/ [UNDER DEV]
	$</bin/pip3 --quiet install cookiecutter
	.venv/bin/cookiecutter gh:itisfoundation/cookiecutter-simcore-pyservice --output-dir $(CURDIR)/services


.PHONY: openapi-specs
openapi-specs: ## bundles and validates openapi specifications and schemas of ALL service's API
	@$(MAKE_C) services/web/server $@
	@$(MAKE_C) services/storage $@
	@$(MAKE_C) services/director $@


.PHONY: code-analysis
code-analysis: .codeclimate.yml ## runs code-climate analysis
	# Validates $<
	./scripts/code-climate.bash validate-config
	# Running analysis
	./scripts/code-climate.bash analyze


.PHONY: auto-doc
auto-doc: .stack-simcore-version.yml ## updates diagrams for README.md
	# Parsing docker-compose config $< and creating graph
	@./scripts/docker-compose-viz.bash $<
	# Updating docs/img
	@mv --verbose $<.png docs/img/


.PHONY: postgres-upgrade
postgres-upgrade: ## initalize or upgrade postgres db to latest state
	@$(MAKE_C) packages/postgres-database/docker build
	@$(MAKE_C) packages/postgres-database/docker upgrade


local_registry=registry
.PHONY: local-registry
local-registry: .env ## creates a local docker registry and configure simcore to use it (NOTE: needs admin rights)
	# add registry to host file
	@echo 127.0.0.1 $(local_registry) >> /etc/hosts
	# allow docker engine to use local insecure registry
	@echo {\"insecure-registries\": [\"$(local_registry):5000\"]} >> /etc/docker/daemon.json
	@service docker restart
	# start registry on port 5000...
	@docker run --detach \
							--init \
							--publish 5000:5000 \
							--volume $(local_registry):/var/lib/registry \
							--name $(local_registry) \
							registry:2
	# set up environment variables to use local registry on port 5000 without any security (take care!)...
	@echo REGISTRY_AUTH=False >> .env
	@echo REGISTRY_SSL=False >> .env
	@echo REGISTRY_URL=$(local_registry):5000 >> .env
	@echo DIRECTOR_REGISTRY_CACHING=False >> .env
	# add registry 172.17.0.1 as extra_host to containers that need access to the registry (e.g. director)


## INFO -------------------------------

.PHONY: info info-images info-swarm  info-tools
info: ## displays setup information
	# setup info:
	@echo ' Detected OS          : $(IS_LINUX)$(IS_OSX)$(IS_WSL)$(IS_WIN)'
	@echo ' SWARM_STACK_NAME     : ${SWARM_STACK_NAME}'
	@echo ' DOCKER_REGISTRY      : $(DOCKER_REGISTRY)'
	@echo ' DOCKER_IMAGE_TAG     : ${DOCKER_IMAGE_TAG}'
	@echo ' BUILD_DATE           : ${BUILD_DATE}'
	@echo ' VCS_* '
	@echo '  - ULR                : ${VCS_URL}'
	@echo '  - REF                : ${VCS_REF}'
	@echo '  - (STATUS)REF_CLIENT : (${VCS_STATUS_CLIENT}) ${VCS_REF_CLIENT}'
	@echo ' DIRECTOR_API_VERSION  : ${DIRECTOR_API_VERSION}'
	@echo ' STORAGE_API_VERSION   : ${STORAGE_API_VERSION}'
	@echo ' WEBSERVER_API_VERSION : ${WEBSERVER_API_VERSION}'
	# tools version
	@echo ' make   : $(shell make --version 2>&1 | head -n 1)'
	@echo ' jq     : $(shell jq --version)'
	@echo ' awk    : $(shell awk -W version 2>&1 | head -n 1)'
	@echo ' python : $(shell python3 --version)'


define show-meta
	$(foreach iid,$(shell docker images */$(1):* -q | sort | uniq),\
		docker image inspect $(iid) | jq '.[0] | .RepoTags, .ContainerConfig.Labels';)
endef

info-images:  ## lists tags and labels of built images. To display one: 'make target=webserver info-images'
ifeq ($(target),)
	@$(foreach service,$(SERVICES_LIST),\
		echo "## $(service) images:";\
			docker images */$(service):*;\
			$(call show-meta,$(service))\
		)
	## Client images:
	@$(MAKE_C) services/web/client info
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
	# Services in 'ops' stack
	-@docker stack services ops
	# Networks
	@docker network ls
endif



## CLEAN -------------------------------

.PHONY: clean clean-images clean-venv clean-all clean-more

_git_clean_args := -dxf -e .vscode -e TODO.md -e .venv
_running_containers = $(shell docker ps -aq)

.check-clean:
	@git clean -n $(_git_clean_args)
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo -n "$(shell whoami), are you REALLY sure? [y/N] " && read ans && [ $${ans:-N} = y ]

clean-venv: devenv ## Purges .venv into original configuration
	# Cleaning your venv
	.venv/bin/pip-sync --quiet $(CURDIR)/requirements.txt
	@pip list

clean: .check-clean ## cleans all unversioned files in project and temp files create by this makefile
	# Cleaning unversioned
	@git clean $(_git_clean_args)
	# Cleaning web/client
	@$(MAKE_C) services/web/client clean-files

clean-more: ## cleans containers and unused volumes
	# stops and deletes running containers
	@$(if $(_running_containers), docker rm -f $(_running_containers),)
	# pruning unused volumes
	docker volume prune --force

clean-images: ## removes all created images
	# Cleaning all service images
	-$(foreach service,$(SERVICES_LIST)\
		,docker image rm -f $(shell docker images */$(service):* -q);)
	# Cleaning webclient
	@$(MAKE_C) services/web/client clean-images
	# Cleaning postgres maintenance
	@$(MAKE_C) packages/postgres-database/docker clean

clean-all: clean clean-more clean-images # Deep clean including .venv and produced images
	-rm -rf .venv


.PHONY: reset
reset: ## restart docker daemon (LINUX ONLY)
	sudo systemctl restart docker

# osparc-simcore general makefile
#
# NOTES:
# 	- GNU make version 4.2 recommended
# 	- Use 'make -n *' to dry-run during debugging
# 	- In windows, only WSL is supported
#
# by sanderegg, pcrespov
.DEFAULT_GOAL := help

# TOOLS --------------------------------------

# Operating system
ifeq ($(filter Windows_NT,$(OS)),)
IS_WSL  := $(if $(findstring Microsoft,$(shell uname -a)),WSL,)
IS_OSX  := $(filter Darwin,$(shell uname -a))
IS_LINUX:= $(if $(or $(IS_WSL),$(IS_OSX)),,$(filter Linux,$(shell uname -a)))
endif

IS_WIN  := $(strip $(if $(or $(IS_LINUX),$(IS_OSX),$(IS_WSL)),,$(OS)))
$(if $(IS_WIN),$(error Windows is not supported in all recipes. Use WSL instead. Follow instructions in README.md),)

SHELL := /bin/bash

# VARIABLES ----------------------------------------------
# TODO: read from docker-compose file instead
SERVICES_LIST := \
	director \
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
export DIRECTOR_API_VERSION := $(shell cat $(CURDIR)/services/director/VERSION)
export STORAGE_API_VERSION  := $(shell cat $(CURDIR)/services/storage/VERSION)
export WEBSERVER_API_VERSION:= $(shell cat $(CURDIR)/services/web/server/VERSION)

# swarm stacks
export SWARM_STACK_NAME ?= simcore

# version tags
export DOCKER_IMAGE_TAG ?= latest
export DOCKER_REGISTRY  ?= itisfoundation

.PHONY: help
help: ## help on rule's targets
ifeq ($(IS_WIN),)
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
else
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
endif



## docker BUILD -------------------------------
#
# - all builds are inmediatly tagged as 'local/{service}:${BUILD_TARGET}' where BUILD_TARGET='development', 'production', 'cache'
# - only production and cache images are released (i.e. tagged pushed into registry)
#
SWARM_HOSTS = $(shell docker node ls --format="{{.Hostname}}" 2>$(if $(IS_WIN),NUL,/dev/null))

.PHONY: build
build: .env ## Builds production images and tags them as 'local/{service-name}:production'. For single target e.g. 'make target=webserver build'
	# Compiling front-end
	@$(MAKE) -C services/web/client compile
ifeq ($(target),)
	# Building services
	@export BUILD_TARGET=production; \
	docker-compose -f services/docker-compose-build.yml build --parallel
else
	# Building service $(target)
	@export BUILD_TARGET=production; \
	docker-compose -f services/docker-compose-build.yml build $(target)
endif

.PHONY: rebuild build-nc
rebuild: build-nc
build-nc: .env ## As build but w/o cache (alias: rebuild)
	# Compiling front-end
	@$(MAKE) -C services/web/client clean compile
ifeq ($(target),)
	# Building services
	@export BUILD_TARGET=production; \
	docker-compose -f services/docker-compose-build.yml build --parallel --no-cache
else
	# Building service $(target)
	@export BUILD_TARGET=production; \
	docker-compose -f services/docker-compose-build.yml build --parallel --no-cache $(target)
endif

.PHONY: build-devel
build-devel: .env ## Builds development images and tags them as 'local/{service-name}:development'. For single target e.g. 'make target=webserver build-devel'
	# Compiling front-end
	@$(MAKE) -C services/web/client touch compile-dev
ifeq ($(target),)
	# Building services
	@export BUILD_TARGET=development; \
	docker-compose -f services/docker-compose-build.yml build --parallel
else
	# Building service $(target)
	@export BUILD_TARGET=development; \
	docker-compose -f services/docker-compose-build.yml build $(target)
endif


.PHONY: build-cache
# TODO: should download cache if any??
build-cache: ## Build cache images and tags them as 'local/{service-name}:cache'
	# Compiling front-end
	@$(MAKE) -C services/web/client compile
	# Building cache images
	@export BUILD_TARGET=cache; \
	docker-compose -f services/docker-compose-build.yml build --parallel


$(CLIENT_WEB_OUTPUT):
	# Ensures source-output folder always exists to avoid issues when mounting webclient->webserver dockers. Supports PowerShell
	-mkdir $(if $(IS_WIN),,-p) $(CLIENT_WEB_OUTPUT)


## docker SWARM -------------------------------
#
# - All resolved configuration are named as .stack-${name}-*.yml to distinguish from docker-compose files which can be parametrized
#
SWARM_HOSTS            = $(shell docker node ls --format="{{.Hostname}}" 2>$(if $(IS_WIN),null,/dev/null))
docker-compose-configs = $(wildcard services/docker-compose*.yml)

.stack-simcore-development.yml: .env $(docker-compose-configs)
	# Creating config for stack with 'local/{service}:development' to $@
	@export DOCKER_REGISTRY=local;       \
	export DOCKER_IMAGE_TAG=development; \
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
	# Deploy stack $(SWARM_STACK_NAME) [back-end]
	@docker stack deploy -c $< $(SWARM_STACK_NAME)
	$(MAKE) .deploy-ops
	# Start compile+watch front-end container [front-end]
	$(if $(IS_WSL),$(warning WINDOWS: Do not forget to run scripts/win-watcher.bat in cmd),)
	$(MAKE) -C services/web/client compile-dev flags=--watch

up-prod: .stack-simcore-production.yml .init-swarm ## Deploys local production stack and ops stack (pass 'make ops_disabled=1 up-...' to disable)
	# Deploy stack $(SWARM_STACK_NAME)
	@docker stack deploy -c $< $(SWARM_STACK_NAME)
	$(MAKE) .deploy-ops

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
	-$(MAKE) -C services/web/client down

leave: ## Forces to stop all services, networks, etc by the node leaving the swarm
	-docker swarm leave -f


.PHONY: .init-swarm
.init-swarm:
	# Ensures swarm is initialized
	$(if $(SWARM_HOSTS),,docker swarm init)


## docker TAGS  -------------------------------

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



## docker PULL/PUSH  -------------------------------
#
# TODO: cannot push modified/untracke
# TODO: cannot push discetedD
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


## PYTHON -------------------------------
.PHONY: pylint

PY_PIP = $(if $(IS_WIN),cd .venv/Scripts && pip.exe,.venv/bin/pip3)

pylint: ## Runs python linter framework's wide
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes
	# TODO: NOT windows friendly
	/bin/bash -c "pylint --rcfile=.pylintrc $(strip $(shell find services packages -iname '*.py' \
											-not -path "*egg*" \
											-not -path "*contrib*" \
											-not -path "*-sdk/python*" \
											-not -path "*generated_code*" \
											-not -path "*datcore.py" \
											-not -path "*web/server*"))"

.PHONY: devenv

.venv:
	python3 -m venv $@
	$@/bin/pip3 install --upgrade \
		pip \
		wheel \
		setuptools

devenv: .venv ## create a python virtual environment with dev tools (e.g. linters, etc)
	$</bin/pip3 install \
		pylint \
		autopep8 \
		pip-tools \
		rope
	@echo "To activate the venv, execute $(if $(IS_WIN),'./venv/Scripts/activate.bat','source .venv/bin/activate')"


## MISC -------------------------------

.PHONY: new-service
new-service: .venv ## Bakes a new project from cookiecutter-simcore-pyservice and drops it under services/ [UNDER DEV]
	$</bin/pip3 install cookiecutter
	.venv/bin/cookiecutter gh:itisfoundation/cookiecutter-simcore-pyservice --output-dir $(CURDIR)/services

# TODO: NOT windows friendly
.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, copying $< ############"; cp $< $@)

# TODO: NOT windows friendly
.vscode/settings.json: .vscode-template/settings.json
	$(info WARNING: #####  $< is newer than $@ ####)
	@diff -uN $@ $<
	@false


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
	@$(MAKE) -C services/web/client info
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


.PHONY: clean clean-images

.check-clean:
	@git clean -ndxf -e .vscode/
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo -n "$(shell whoami), are you REALLY sure? [y/N] " && read ans && [ $${ans:-N} = y ]

clean: .check-clean ## cleans all unversioned files in project and temp files create by this makefile
	# Cleaning unversioned
	@git clean -dxf -e .vscode/
	# Cleaning web/client
	@$(MAKE) -C services/web/client clean

clean-images: ## removes all created images
	# Cleaning all service images
	-$(foreach service,$(SERVICES_LIST)\
		,docker image rm -f $(shell docker images */$(service):* -q);)
	# Cleaning webclient
	@$(MAKE) -C services/web/client clean


.PHONY: reset
reset: ## restart docker daemon
	sudo systemctl restart docker

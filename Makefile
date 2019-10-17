# osparc-simcore general makefile
#
# Recommended: GNU make version 4.2
#
# by sanderegg, pcrespov

PREDEFINED_VARIABLES := $(.VARIABLES)

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
	apihub \
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

# swarm stacks
export SWARM_STACK_NAME ?= simcore

# version tags
export DOCKER_IMAGE_TAG ?= latest
export DOCKER_REGISTRY  ?= itisfoundation

.PHONY: help
help: ## displays targets
ifeq ($(IS_WIN),)
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
else
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
endif

.DEFAULT_GOAL := help


## docker BUILD -------------------------------
#
# - all builds are inmediatly tagged as 'local/{service}:${BUILD_TARGET}' where BUILD_TARGET='development', 'production', 'cache'
# - only production and cache images are released (i.e. tagged pushed into registry)
#

SWARM_HOSTS = $(shell docker node ls --format="{{.Hostname}}" 2>$(if $(IS_WIN),NUL,/dev/null))

.PHONY: build
build: .env ## Builds production images and tags them as 'local/{service-name}:production'
	# Compiling front-end
	@$(MAKE) -C services/web/client compile
	# Building services
	@export BUILD_TARGET=production; \
	docker-compose -f services/docker-compose.build.yml build --parallel


.PHONY: rebuild build-nc
rebuild: build-nc
build-nc: .env ## As build but w/o cache (alias: rebuild)
	# Compiling front-end
	@$(MAKE) -C services/web/client clean compile
	# Building services
	@export BUILD_TARGET=production; \
	docker-compose -f services/docker-compose.build.yml build --parallel --no-cache


.PHONY: build-devel
build-devel: .env ## Builds development images and tags them as 'local/{service-name}:development'
	# Compiling front-end
	@$(MAKE) -C services/web/client compile-dev
	# Building services
	@export BUILD_TARGET=development; \
	docker-compose -f services/docker-compose.build.yml build --parallel


.PHONY: build-cache
# TODO: should download cache if any??
build-cache: ## Build cache images and tags them as 'local/{service-name}:cache'
	# Compiling front-end
	@$(MAKE) -C services/web/client compile
	# Building cache images
	@export BUILD_TARGET=cache; \
	docker-compose -f services/docker-compose.build.yml build --parallel


$(CLIENT_WEB_OUTPUT):
	# Ensures source-output folder always exists to avoid issues when mounting webclient->webserver dockers. Supports PowerShell
	-mkdir $(if $(IS_WIN),,-p) $(CLIENT_WEB_OUTPUT)


## docker SWARM -------------------------------
SWARM_HOSTS       = $(shell docker node ls --format="{{.Hostname}}" 2>$(if $(IS_WIN),null,/dev/null))

# docker-compose configs---

docker-compose-configs = $(wildcard services/docker-compose*.yml)

.docker-compose-development.yml: .env $(docker-compose-configs)
	# Creating config for stack with 'local/{service}:development' to $@
	@export DOCKER_REGISTRY=local;       \
	export DOCKER_IMAGE_TAG=development; \
	docker-compose -f services/docker-compose.yml -f services/docker-compose.local.yml -f services/docker-compose.devel.yml --log-level=ERROR config > $@

.docker-compose-production.yml: .env $(docker-compose-configs)
	# Creating config for stack with 'local/{service}:production' to $@
	@export DOCKER_REGISTRY=local;       \
	export DOCKER_IMAGE_TAG=production; \
	docker-compose -f services/docker-compose.yml -f services/docker-compose.local.yml --log-level=ERROR config > $@

.docker-compose-version.yml: .env $(docker-compose-configs)
	# Creating config for stack with '$(DOCKER_REGISTRY)/{service}:${DOCKER_IMAGE_TAG}' to $@
	@docker-compose -f services/docker-compose.yml -f services/docker-compose.local.yml --log-level=ERROR config > $@


.PHONY: up-devel up-prod up-version up-latest up-ops

define deploy_ops_stack
	@docker stack deploy -c $(CURDIR)/services/docker-compose-ops.yml ops
endef

up-devel: .docker-compose-development.yml .init-swarm $(CLIENT_WEB_OUTPUT) ## Deploys local development stack, tools and qx-compile+watch
	# Deploy stack $(SWARM_STACK_NAME) [back-end]
	@docker stack deploy -c .docker-compose-development.yml $(SWARM_STACK_NAME)
	# Deploy stack 'ops'
	@$(call deploy_ops_stack)
	# Start compile+watch front-end container [front-end]
	$(if $(IS_WSL),$(warning WINDOWS: Do not forget to run scripts/win-watcher.bat in cmd),)
	## $(MAKE) -C services/web/client compile-dev flags=--watch

up-prod: .docker-compose-production.yml .init-swarm ## Deploys local production stack and tooling
	# Deploy stack $(SWARM_STACK_NAME)
	@docker stack deploy -c .docker-compose-production.yml $(SWARM_STACK_NAME)
	# Deploy stack 'ops'
	@$(call deploy_ops_stack)


up-version: .docker-compose-version.yml .init-swarm ## Deploys stack of services '$(DOCKER_REGISTRY)/{service}:$(DOCKER_IMAGE_TAG)'
	# Deploy stack $(SWARM_STACK_NAME)
	@docker stack deploy -c .docker-compose-version.yml $(SWARM_STACK_NAME)
	# Deploy stack 'ops'
	@$(call deploy_ops_stack)


up-latest:
	@export DOCKER_IMAGE_TAG=latest; \
	$(MAKE) up-version


up-ops: .init-swarm ## Deploys ONLY ops stack (subset of some services in osparc-ops)
	@$(call deploy_ops_stack)


.PHONY: down leave
down: ## Stops and removes stack
	# Removing stack '$(SWARM_STACK_NAME)'
	-docker stack rm $(SWARM_STACK_NAME)
	# Removing stack 'ops'
	-docker stack rm ops
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

devenv: .venv ## creates a python virtual environment with development tools (e.g. pip, pylint, pip-tools, etc ...)
.venv:
	$(if $(IS_WIN),python.exe,python3) -m venv .venv
	$(PY_PIP) install --upgrade pip wheel setuptools
	$(PY_PIP) install pylint autopep8 virtualenv pip-tools
	@echo "To activate the venv, execute $(if $(IS_WIN),'./venv/Scripts/activate.bat','source .venv/bin/activate')"


## MISC -------------------------------

.PHONY: new-service
new-service: .venv ## Bakes a new project from cookiecutter-simcore-pyservice and drops it under services/ [UNDER DEV]
	$(PY_PIP) install cookiecutter
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

PHONY: setup-check
setup-check: .env .vscode/settings.json ## checks whether setup is in sync with templates (e.g. vscode settings or .env file)


.PHONY: info info-images info-swarm info-vars info-tools
info: ## displays selected information
	# setup
	@echo ' Detected OS          : $(IS_LINUX)$(IS_OSX)$(IS_WSL)$(IS_WIN)'
	@echo ' SWARM_STACK_NAME     : ${SWARM_STACK_NAME}'
	@echo ' DOCKER_REGISTRY      : $(DOCKER_REGISTRY)'
	@echo ' DOCKER_IMAGE_TAG     : ${DOCKER_IMAGE_TAG}'
	@echo ' BUILD_DATE           : ${BUILD_DATE}'
	@echo ' VCS_* '
	@echo '  - ULR                : ${VCS_URL}'
	@echo '  - REF                : ${VCS_REF}'
	@echo '  - (STATUS)REF_CLIENT : (${VCS_STATUS_CLIENT}) ${VCS_REF_CLIENT}'


info-tools: ## displays tools in place
	$(info make   : $(shell make --version 2>&1 | head -n 1) )
	$(info jq     : $(shell jq --version)   )
	$(info awk    : $(shell awk -W version 2>&1 | head -n 1) )
	$(info python : $(shell python3 --version))
	#


info-vars: ## displays all parameters of makefile environments (makefile debugging)
	$(info VARIABLES ------------)
	$(foreach v,                                                                                  \
		$(filter-out $(PREDEFINED_VARIABLES) PREDEFINED_VARIABLES PY_FILES, $(sort $(.VARIABLES))), \
		$(info $(v)=$($(v)) [in $(origin $(v))])                                                    \
	)
	#

define show-meta
	$(foreach iid,$(shell docker images */$(1):* -q | sort | uniq),\
		docker image inspect $(iid) | jq '.[0] | .RepoTags, .ContainerConfig.Labels';)
endef

info-image: ## list image tags and labels for a given service. E.g. make info-image service=webserver
	## $(service) images:
	$(call show-meta, $(service))

info-images:  ## lists created images (mostly for debugging makefile)
	@$(foreach service,$(SERVICES_LIST),\
		echo "## $(service) images:";\
			docker images */$(service):*;\
			$(call show-meta,$(service))\
		)
	## Client images:
	@$(MAKE) -C services/web/client info

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

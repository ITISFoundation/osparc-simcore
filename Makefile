# osparc-simcore general makefile
#
# TODO: make fully windows-friendly (e.g. some tools to install or replace e.g. mktemp, ...  )
#
# Recommended: GNU make version 4.2
#
# by sanderegg, pcrespov

PREDEFINED_VARIABLES := $(.VARIABLES)

# TOOLS --------------------------------------

# Operating system
ifeq ($(filter Windows_NT,$(OS)),)
IS_LINUX:= $(filter Linux,$(shell uname))
IS_OSX  := $(filter Darwin,$(shell uname))
else
IS_WSL  := $(filter Microsoft,$(shell uname))
endif
IS_WIN  := $(strip $(if $(or $(IS_LINUX),$(IS_OSX),$(IS_WSL)),,$(OS)))

$(info + Detected OS : $(IS_LINUX)$(IS_OSX)$(IS_WSL)$(IS_WIN))

# Makefile's shell
SHELL := $(if $(IS_WIN),powershell.exe,/bin/bash)


DOCKER_COMPOSE=$(if $(IS_WIN),docker-compose.exe,docker-compose)
DOCKER        =$(if $(IS_WIN),docker.exe,docker)



# VARIABLES ----------------------------------------------
# TODO: read from docker-compose file instead
SERVICES_LIST := \
	apihub \
	director \
	sidecar \
	storage \
	webserver

CLIENT_WEB_OUTPUT       := $(CURDIR)/services/web/client/source-output

export VCS_URL          := $(shell git config --get remote.origin.url)
export VCS_REF          := $(shell git rev-parse --short HEAD)
export VCS_REF_CLIENT   := $(shell git log --pretty=tformat:"%h" -n1 services/web/client)
export VCS_STATUS_CLIENT:= $(if $(shell git status -s),'modified/untracked','clean')
export BUILD_DATE       := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
export SWARM_STACK_NAME ?= simcore
export DOCKER_IMAGE_TAG ?= latest
export DOCKER_REGISTRY  ?= itisfoundation

$(foreach v, \
	SWARM_STACK_NAME DOCKER_IMAGE_TAG DOCKER_REGISTRY DOCKER_REGISTRY_NEW, \
	$(info + $(v) set to '$($(v))'))


## DOCKER BUILD -------------------------------
TEMP_SUFFIX      := $(strip $(SWARM_STACK_NAME)_docker-compose.yml)
TEMP_COMPOSE_YML := $(shell $(if $(IS_WIN), (New-TemporaryFile).FullName, mktemp --suffix=$(TEMP_SUFFIX)))
SWARM_HOSTS       = $(shell $(DOCKER) node ls --format="{{.Hostname}}" 2>$(if IS_WIN,null,/dev/null))


.PHONY: config
create-stack-file: config # TODO: deprecate create-stack-file
config: ## Creates deploy stack file for production as $(output_file) e.g. 'make config output_file=stack.yaml'
	$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose.prod.yml config > $(output_file)


.PHONY: build
build: .env ## Builds all core service images (user 'make build-nc' to build w/o cache)
	# Compiling front-end
	$(MAKE) -C services/web/client compile
	# Building services
	export BUILD_TARGET=production; \
	$(DOCKER_COMPOSE) -f services/docker-compose.build.yml build --parallel


.PHONY: rebuild build-nc
rebuild: build-nc #TODO: deprecate rebuild
build-nc: .env
	# Compiling front-end
	$(MAKE) -C services/web/client clean compile
	# Building services
	export BUILD_TARGET=production; \
	$(DOCKER_COMPOSE) -f services/docker-compose.build.yml build --no-cache --parallel


.PHONY: build-devel
build-devel: .env ## Builds images of core services for development
	# Compiling front-end ('compile' target needed since productions stage in Dockerfile of webserver copies client/tools/qooxdoo-kit/build:latest)
	$(MAKE) -C services/web/client compile compile-dev
	# Building services
	export BUILD_TARGET=development; \
	$(DOCKER_COMPOSE) -f services/docker-compose.build.yml -f services/docker-compose.devel.yml build --parallel


$(CLIENT_WEB_OUTPUT):
	# Ensures source-output folder always exists to avoid issues when mounting webclient->webserver dockers. Supports PowerShell
	-mkdir $(if $(IS_WIN),,-p) $(CLIENT_WEB_OUTPUT)


## DOCKER SWARM -------------------------------
.PHONY: up up-devel
up: .env .init-swarm ## deploys production stack + tools
	# config stack to $(TEMP_COMPOSE_YML)
	@$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose-tools.yml config > $(TEMP_COMPOSE_YML);
	# deploy stack $(SWARM_STACK_NAME)
	@$(DOCKER) stack deploy -c $(TEMP_COMPOSE_YML) $(SWARM_STACK_NAME)

up-devel: .env .init-swarm $(CLIENT_WEB_OUTPUT) ## deploys development stack and qx-compile+watch
	# config devel stack to $(TEMP_COMPOSE_YML)
	$(DOCKER_COMPOSE) $(addprefix -f services/docker-compose, .yml .devel.yml -tools.yml) config > $(TEMP_COMPOSE_YML)
	# deploy devel stack
	@$(DOCKER) stack deploy -c $(TEMP_COMPOSE_YML) $(SWARM_STACK_NAME)
	# start compile+watch front-end container
	$(MAKE) -C services/web/client compile-dev flags=--watch


.PHONY: up-webclient-devel
up-webclient-devel: up-devel ## as up-devel but with continuous compile of the front-end
	# start compile+watch front-end container
	$(MAKE) -C services/web/client compile-dev flags=--watch


.PHONY: down down-force
down: ## stops and removes stack
	$(DOCKER) stack rm $(SWARM_STACK_NAME)

down-force: ## forces to stop all services and leave swarms
	$(DOCKER) swarm leave -f


.PHONY: .init-swarm
.init-swarm:
	# Ensures swarm is initialized
	$(if $(SWARM_HOSTS),,$(DOCKER) swarm init)


## DOCKER REGISTRY  -------------------------------
.PHONY: pull-cache
pull-cache: .env
	$(DOCKER_COMPOSE) -f services/docker-compose.cache.yml pull

.PHONY: build-cache
build-cache: ## Builds service images and tags them as 'cache'
	$(DOCKER_COMPOSE) -f services/docker-compose.build.yml -f services/docker-compose.cache.yml build --parallel


.PHONY: push-cache
push-cache: ## Pushes service images tagged as 'cache' into the registry
	$(DOCKER_COMPOSE) -f services/docker-compose.cache.yml push ${SERVICES_LIST}

.PHONY: tag push pull
tag: ## tags service images
ifndef DOCKER_REGISTRY_NEW
	$(error DOCKER_REGISTRY_NEW variable is undefined)
endif
ifndef DOCKER_IMAGE_TAG_NEW
	$(error DOCKER_IMAGE_TAG_NEW variable is undefined)
endif
	@echo "Tagging from $(DOCKER_REGISTRY), ${DOCKER_IMAGE_TAG} to ${DOCKER_REGISTRY_NEW}, ${DOCKER_IMAGE_TAG_NEW}"
	$(foreach service, $(SERVICES_LIST)\
		,$(DOCKER) tag $(DOCKER_REGISTRY)/$(service):${DOCKER_IMAGE_TAG} ${DOCKER_REGISTRY_NEW}/$(service):$(DOCKER_IMAGE_TAG_NEW); \
	)

push: ## Pushes images of $(SERVICES_LIST) into a registry
	$(DOCKER_COMPOSE) -f services/docker-compose.yml push $(SERVICES_LIST)

pull: .env ## Pulls images of $(SERVICES_LIST) from a registry
	$(DOCKER_COMPOSE) -f services/docker-compose.yml pull $(SERVICES_LIST)


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

.venv: ## creates a python virtual environment with dev tools (pip, pylint, ...)
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
	@echo "WARMING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, copying $< ############"; cp $< $@)

# TODO: NOT windows friendly
.vscode/settings.json: .vscode-template/settings.json
	$(info WARNING: #####  $< is newer than $@ ####)
	@diff -uN $@ $<
	@false

PHONY: setup-check
setup-check: .env .vscode/settings.json ## checks whether setup is in sync with templates (e.g. vscode settings or .env file)

.PHONY: info
info: ## displays selected parameters of makefile environments
	@echo '+ "$(shell make --version)"'
	@echo '+ VCS_* '
	@echo '  - ULR                : ${VCS_URL}'
	@echo '  - REF                : ${VCS_REF}'
	@echo '  - (STATUS)REF_CLIENT : (${VCS_STATUS_CLIENT}) ${VCS_REF_CLIENT}'
	@echo '+ BUILD_DATE           : ${BUILD_DATE}'
	@echo '+ DOCKER_REGISTRY      : $(DOCKER_REGISTRY)'
	@echo '+ DOCKER_IMAGE_TAG     : ${DOCKER_IMAGE_TAG}'


.PHONY: info-more
info-more: ## displays all parameters of makefile environments
	$(info VARIABLES ------------)
	$(foreach v,                                                                                  \
		$(filter-out $(PREDEFINED_VARIABLES) PREDEFINED_VARIABLES PY_FILES, $(sort $(.VARIABLES))), \
		$(info $(v)=$($(v)) [in $(origin $(v))])                                                    \
	)
	@echo "----"
ifneq ($(SWARM_HOSTS), )
	@echo ""
	$(DOCKER) stack ls
	@echo ""
	-$(DOCKER) stack ps $(SWARM_STACK_NAME)
	@echo ""
	-$(DOCKER) stack services $(SWARM_STACK_NAME)
	@echo ""
	$(DOCKER) network ls
endif


.PHONY: clean
# TODO: does not clean windows temps
clean:   ## cleans all unversioned files in project and temp files create by this makefile
	# cleaning web/client
	$(MAKE) -C services/web/client clean
	# removing temps
	@-rm $(wildcard $(dir $(shell mktemp -u))*$(TEMP_SUFFIX))
	# removing unversioned
	@git clean -dxf -e .vscode/


.PHONY: reset
reset: ## restart docker daemon
	sudo systemctl restart docker


.PHONY: help
help: ## display all callable targets
ifeq ($(IS_WIN),)
	@sort $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
else
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
endif

.DEFAULT_GOAL := help

# osparc-simcore general makefile
#
# TODO: make fully windows-friendly (e.g. some tools to install or replace e.g. date, ...  )
#
# by sanderegg, pcrespov
#
PREDEFINED_VARIABLES := $(.VARIABLES)

# Operating system
ifeq ($(filter Windows_NT,$(OS)),)
IS_LINUX:= $(filter Linux,$(shell uname))
IS_OSX  := $(filter Darwin,$(shell uname))
else
IS_WSL  := $(filter Microsoft,$(shell uname))
endif
IS_WIN  := $(if $(or IS_LINUX,IS_OSX,IS_WSL),,$(OS))

# Makefile's shell
SHELL = $(if $(IS_WIN),cmd.exe,/bin/bash)



VERSION := $(shell uname -a)

# SAN: this is a hack so that docker-compose works in the linux virtual environment under Windows
WINDOWS_MODE=OFF
ifneq (,$(findstring Microsoft,$(VERSION)))
$(info    detected WSL)
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
# SAN: Windows does not have these things defined... but they are needed to execute a local swarm
WINDOWS_MODE=ON
else ifeq ($(OS), Windows_NT)
$(info    detected Powershell/CMD)
export DOCKER_COMPOSE=docker-compose.exe
export DOCKER=docker.exe
WINDOWS_MODE=ON
else ifneq (,$(findstring Darwin,$(VERSION)))
$(info    detected OSX)
SHELL = /bin/bash
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
else
$(info    detected native linux)
SHELL = /bin/bash
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
endif

PY_FILES := $(strip $(shell find services packages -iname '*.py' \
											-not -path "*egg*" \
											-not -path "*contrib*" \
											-not -path "*-sdk/python*" \
											-not -path "*generated_code*" \
											-not -path "*datcore.py" \
											-not -path "*web/server*"))
TEMPCOMPOSE := $(shell mktemp)

SERVICES_LIST := apihub director sidecar storage webserver maintenance
CACHED_SERVICES_LIST := apihub director sidecar storage webserver webclient
CLIENT_WEB_OUTPUT:=$(CURDIR)/services/web/client/source-output

export VCS_URL:=$(shell git config --get remote.origin.url)
export VCS_REF:=$(shell git rev-parse --short HEAD)
export VCS_REF_CLIENT:=$(shell git log --pretty=tformat:"%h" -n1 services/web/client)
export VCS_STATUS_CLIENT:=$(if $(shell git status -s),'modified/untracked','clean')
export BUILD_DATE:=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
export SWARM_STACK_NAME ?= services
# using ?= will only set if absent
export DOCKER_IMAGE_TAG ?= latest
$(info DOCKER_IMAGE_TAG set to ${DOCKER_IMAGE_TAG})

# default to local (no registry)
export DOCKER_REGISTRY ?= itisfoundation
$(info DOCKER_REGISTRY set to $(DOCKER_REGISTRY))

# TOOLS
MKDIR = $(if $(IS_WIN),md,mkdir -p)
RM    = $(if $(IS_WIN),del /Q,rm)

## -------------------------------
# Docker build and composition

.PHONY: build
build: .env .tmp-webclient-build ## Builds all core service images.
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build --parallel ${SERVICES_LIST}

.PHONY: rebuild
rebuild: .env .tmp-webclient-build ## Builds all core service images.
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build --no-cache --parallel ${SERVICES_LIST}

.PHONY: build-devel .tmp-webclient-build
build-devel: .env .tmp-webclient-build ## Builds images of core services for development (in parallel).
	$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose.devel.yml build --parallel

# TODO: fixes having services_webclient:build present for services_webserver:production when
# targeting services_webserver:development and
.tmp-webclient-build: $(CLIENT_WEB_OUTPUT)
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build webclient

$(CLIENT_WEB_OUTPUT):
	# Ensures source-output folder always exists to avoid issues when mounting webclient->webserver dockers. Supports PowerShell
	$(MKDIR) $(CLIENT_WEB_OUTPUT)


.PHONY: build-client rebuild-client
# target: build-client, rebuild-client: – Builds only webclient and webserver images. Use `rebuild` to build w/o cache
build-client: .env
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build webclient
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build webserver

rebuild-client: .env
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build --no-cache webclient
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build --no-cache webserver


.PHONY: init-swarm up up-devel up-devel remove-intermediate-file down down-swarm
SWARM_HOSTS = $(shell $(DOCKER) node ls --format={{.Hostname}} 2>/dev/null)

init-swarm: ## initializes swarm
	$(if $(SWARM_HOSTS), \
		, \
		$(DOCKER) swarm init \
	)

up: .env init-swarm ## init swarm and deploys all core and tool services up [-devel suffix uses container in development mode]
	$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose-tools.yml config > $(TEMPCOMPOSE).tmp-compose.yml ;
	@$(DOCKER) stack deploy -c $(TEMPCOMPOSE).tmp-compose.yml ${SWARM_STACK_NAME}

up-devel: .env init-swarm $(CLIENT_WEB_OUTPUT)
	$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose.devel.yml -f services/docker-compose-tools.yml config > $(TEMPCOMPOSE).tmp-compose.yml
	@$(DOCKER) stack deploy -c $(TEMPCOMPOSE).tmp-compose.yml ${SWARM_STACK_NAME}

up-swarm: up
up-swarm-devel: up-devel

.PHONY: up-webclient-devel
up-webclient-devel: up-devel remove-intermediate-file ## init swarm and deploys all core and tool services up in development mode. Then it stops the webclient service and starts it again with the watcher attached.
	$(DOCKER) service rm services_webclient
	$(DOCKER_COMPOSE) -f services/web/client/docker-compose.yml up qx

remove-intermediate-file:
	-$(RM) $(TEMPCOMPOSE).tmp-compose.yml

down: down-swarm ## forces to stop all services and leave swarm
down-swarm:
	$(DOCKER) swarm leave -f


.PHONY: pull-cache
pull-cache: .env
	$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose.cache.yml pull

.PHONY: build-cache
build-cache: ## Builds service images and tags them as 'cache'
	# WARNING: first all except webserver and then webserver
	$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose.cache.yml build --parallel apihub director sidecar storage webclient maintenance
	$(DOCKER) tag $(DOCKER_REGISTRY)/webclient:cache services_webclient:build
	$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose.cache.yml build webserver


.PHONY: push-cache
push-cache: ## Pushes service images tagged as 'cache' into the registry
	$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose.cache.yml push ${CACHED_SERVICES_LIST}



## -------------------------------
# registry operations
ifdef DOCKER_REGISTRY_NEW
$(info DOCKER_REGISTRY_NEW set to ${DOCKER_REGISTRY_NEW})
endif # DOCKER_REGISTRY_NEW

.PHONY: tag push pull create-stack-file
tag: ## tags service images
ifndef DOCKER_REGISTRY_NEW
	$(error DOCKER_REGISTRY_NEW variable is undefined)
endif
ifndef DOCKER_IMAGE_TAG_NEW
	$(error DOCKER_IMAGE_TAG_NEW variable is undefined)
endif
	@echo "Tagging from $(DOCKER_REGISTRY), ${DOCKER_IMAGE_TAG} to ${DOCKER_REGISTRY_NEW}, ${DOCKER_IMAGE_TAG_NEW}"
	@for i in $(SERVICES_LIST); do \
		$(DOCKER) tag $(DOCKER_REGISTRY)/$$i:${DOCKER_IMAGE_TAG} ${DOCKER_REGISTRY_NEW}/$$i:${DOCKER_IMAGE_TAG_NEW}; \
	done

push: ## Pushes images into a registry
	$(DOCKER_COMPOSE) -f services/docker-compose.yml push ${SERVICES_LIST}

pull: .env ## Pulls images from a registry
	$(DOCKER_COMPOSE) -f services/docker-compose.yml pull ${SERVICES_LIST}


create-stack-file: use as 'make create-stack-file output_file=stack.yaml'
	$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose.prod.yml config > $(output_file)


## MISC -------------------------------

.PHONY: pylint
pylint: ## Runs python linter framework's wide
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes
	/bin/bash -c "pylint --rcfile=.pylintrc $(PY_FILES)"


.PHONY: new-service
new-service: ## Bakes a new project from cookiecutter-simcore-pyservice and drops it under services/
	.venv/bin/cookiecutter gh:itisfoundation/cookiecutter-simcore-pyservice --output-dir $(CURDIR)/services


## -------------------------------
# Virtual Environments

.env: .env-devel ## creates .env file from defaults in .env-devel
	# first check if file exists, copies it
	@if [ ! -f $@ ]	; then \
		echo "##### $@ does not exist, copying $< ############"; \
		cp $< $@; \
	else \
		echo "#####  $< is newer than $@ ####"; \
		diff -uN $@ $<; \
		false; \
	fi

.vscode/settings.json: .vscode-template/settings.json
	$(info #####  $< is newer than $@ ####)
	@diff -uN $@ $<
	@false

PHONY: setup-check
setup-check: .env .vscode/settings.json ## Checks whether setup is in sync with templates (e.g. vscode settings or .env file)

.venv: ## creates a python virtual environment with dev tools (pip, pylint, ...)
	python3 -m venv .venv
	.venv/bin/pip3 install --upgrade pip wheel setuptools
	.venv/bin/pip3 install pylint autopep8 virtualenv pip-tools
	@echo "To activate the venv, execute 'source .venv/bin/activate'"


## -------------------------------
# Auxiliary targets.

.PHONY: info
info: ## displays selected parameters of makefile environments
	@echo '+ VCS_* '
	@echo '  - ULR                : ${VCS_URL}'
	@echo '  - REF                : ${VCS_REF}'
	@echo '  - (STATUS)REF_CLIENT : (${VCS_STATUS_CLIENT}) ${VCS_REF_CLIENT}'
	@echo '+ BUILD_DATE           : ${BUILD_DATE}'
	@echo '+ VERSION              : ${VERSION}'
	@echo '+ WINDOWS_MODE         : ${WINDOWS_MODE}'
	@echo '+ DOCKER_REGISTRY      : $(DOCKER_REGISTRY)'
	@echo '+ DOCKER_IMAGE_TAG     : ${DOCKER_IMAGE_TAG}'
	@echo '+ SERVICES_VERSION     : ${SERVICES_VERSION}'
	@echo '+ PY_FILES             : $(shell echo $(PY_FILES) | wc -w) files'

.PHONY: info-detail
info-detail: ## displays all parameters of makefile environments
	$(info VARIABLES ------------)
	$(foreach v,                                                                                  \
		$(filter-out $(PREDEFINED_VARIABLES) PREDEFINED_VARIABLES PY_FILES, $(sort $(.VARIABLES))), \
		$(info $(v)=$($(v))     [in $(origin $(v))])                                                \
	)
	@echo ""

.PHONY: reset
reset: ## restart docker daemon
	sudo systemctl restart docker

.PHONY: clean
clean: remove-intermediate-file ## cleans all unversioned files in project
	@git clean -dxf -e .vscode/

.PHONY: help
help: ## display all callable targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-.]+:.*?## / {printf $(if $(IS_WIN),"%-20s %s/n","\033[36m%-20s\033[0m %s\n"), $$1, $$2}' $(MAKEFILE_LIST)

.DEFAULT_GOAL := help

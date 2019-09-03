# osparc-simcore general makefile
#
# TODO: make fully windows-friendly (e.g. some tools to install or replace e.g. date, ...  )
#
# Recommended
#   GNU make version 4.2
#
# by sanderegg, pcrespov
#
PREDEFINED_VARIABLES := $(.VARIABLES)

# TOOLS --------------------------------------

# Operating system
ifeq ($(filter Windows_NT,$(OS)),)
IS_LINUX:= $(filter Linux,$(shell uname))
IS_OSX  := $(filter Darwin,$(shell uname))
else
IS_WSL  := $(filter Microsoft,$(shell uname))
endif
IS_WIN  := $(if $(or IS_LINUX,IS_OSX,IS_WSL),,$(OS))

$(info Detected OS : $(IS_LINUX) $(IS_OSX) $(IS_WSL) $(IS_WIN))


# Makefile's shell
SHELL = $(if $(IS_WIN),cmd.exe,/bin/bash)

export MKDIR  = $(if $(IS_WIN),md,mkdir -p)
export RM     = $(if $(IS_WIN),del /Q,rm)
export MKTEMP = $(if $(IS_WIN),\
	set "tmpdir=%temp%\mktemp~%RANDOM%" && md %tmpdir% && echo %tmpdir%,\
	mktemp)

export DOCKER_COMPOSE=$(if $(IS_WIN),docker-compose.exe,docker-compose)
export DOCKER        =$(if $(IS_WIN),docker.exe,docker)



# VARIABLES ----------------------------------------------
SERVICES_LIST := \
	apihub \
	director \
	sidecar \
	storage \
	webserver

CACHED_SERVICES_LIST := $(join $(SERVICE_LIST), webclient)
CLIENT_WEB_OUTPUT    :=$(CURDIR)/services/web/client/source-output

export VCS_URL:=$(shell git config --get remote.origin.url)
export VCS_REF:=$(shell git rev-parse --short HEAD)
export VCS_REF_CLIENT:=$(shell git log --pretty=tformat:"%h" -n1 services/web/client)
export VCS_STATUS_CLIENT:=$(if $(shell git status -s),'modified/untracked','clean')
export BUILD_DATE:=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
export SWARM_STACK_NAME ?= simcore
# using ?= will only set if absent
export DOCKER_IMAGE_TAG ?= latest
# default to local (no registry)
export DOCKER_REGISTRY ?= itisfoundation

$(foreach v, \
	SWARM_STACK_NAME DOCKER_IMAGE_TAG DOCKER_REGISTRY, \
	$(info + $(v) set to '$($(v))'))


## DOCKER BUILD -------------------------------

TEMPCOMPOSE := $(shell $(MKTEMP))
SWARM_HOSTS = $(shell $(DOCKER) node ls --format={{.Hostname}} 2>/dev/null)

create-stack-file: ## Creates stack file for production as $(output_file) e.g. 'make create-stack-file output_file=stack.yaml'
	$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose.prod.yml config > $(output_file)

.PHONY: build
build: .env .build-webclient ## Builds all core service images (user `make rebuild` to build w/o cache)
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build --parallel $(SERVICES_LIST)

.PHONY: rebuild
rebuild: .env .build-webclient
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build --no-cache --parallel $(SERVICES_LIST)

.PHONY: build-devel
build-devel: .env .build-webclient ## Builds images of core services for development
	$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose.devel.yml build --parallel


.PHONY: .build-webclient
# fixes having services_webclient:build present for services_webserver:production when targeting services_webserver:development
.build-webclient: $(CLIENT_WEB_OUTPUT)
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build webclient

$(CLIENT_WEB_OUTPUT):
	# Ensures source-output folder always exists to avoid issues when mounting webclient->webserver dockers. Supports PowerShell
	$(MKDIR) $(CLIENT_WEB_OUTPUT)


.PHONY: build-client rebuild-client
build-client: .env ## Builds only webclient and webserver images. Use `rebuild` to build w/o cache
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build webclient
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build webserver

rebuild-client: .env
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build --no-cache webclient
	$(DOCKER_COMPOSE) -f services/docker-compose.yml build --no-cache webserver


## DOCKER SWARM -------------------------------

.PHONY: up up-devel
up: .env .init-swarm ## init swarm and deploys all core and tool services up [-devel suffix uses container in development mode]
	$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose-tools.yml config > $(TEMPCOMPOSE).tmp-compose.yml ;
	@$(DOCKER) stack deploy -c $(TEMPCOMPOSE).tmp-compose.yml $(SWARM_STACK_NAME)

up-devel: .env .init-swarm $(CLIENT_WEB_OUTPUT)
	$(DOCKER_COMPOSE) -f services/docker-compose.yml -f services/docker-compose.devel.yml -f services/docker-compose-tools.yml config > $(TEMPCOMPOSE).tmp-compose.yml
	@$(DOCKER) stack deploy -c $(TEMPCOMPOSE).tmp-compose.yml $(SWARM_STACK_NAME)

.PHONY: up-webclient-devel
up-webclient-devel: up-devel .remove-intermediate-file ## init swarm and deploys all core and tool services up in development mode. Then it stops the webclient service and starts it again with the watcher attached.
	$(DOCKER) service rm services_webclient
	$(DOCKER_COMPOSE) -f services/web/client/docker-compose.yml up qx


.PHONY: down down-force
down: ## stops and removes stack
	docker stack rm $(SWARM_STACK_NAME)

down-force: ## forces to stop all services and leave swarms
	$(DOCKER) swarm leave -f


.PHONY: .remove-intermediate-file
.remove-intermediate-file:
	-$(RM) $(TEMPCOMPOSE).tmp-compose.yml

.PHONY: .init-swarm
.init-swarm:
	# ensures swarm is initialized
	$(if $(SWARM_HOSTS),,$(DOCKER) swarm init)


## DOCKER REGISTRY  -------------------------------

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

ifdef DOCKER_REGISTRY_NEW
$(info DOCKER_REGISTRY_NEW set to ${DOCKER_REGISTRY_NEW})
endif # DOCKER_REGISTRY_NEW

.PHONY: tag push pull create-stack-file
#TODO: does not work in windows
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

push: ## Pushes images of $(SERVICES_LIST) into a registry
	$(DOCKER_COMPOSE) -f services/docker-compose.yml push $(SERVICES_LIST)

pull: .env ## Pulls images of $(SERVICES_LIST) from a registry
	$(DOCKER_COMPOSE) -f services/docker-compose.yml pull $(SERVICES_LIST)



## PYTHON -------------------------------
.PHONY: pylint

#TODO: does not work in windows
PY_FILES = $(strip $(shell find services packages -iname '*.py' \
											-not -path "*egg*" \
											-not -path "*contrib*" \
											-not -path "*-sdk/python*" \
											-not -path "*generated_code*" \
											-not -path "*datcore.py" \
											-not -path "*web/server*"))

pylint: ## Runs python linter framework's wide
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes
	/bin/bash -c "pylint --rcfile=.pylintrc $(PY_FILES)"

.venv: ## creates a python virtual environment with dev tools (pip, pylint, ...)
	python3 -m venv .venv
	.venv/bin/pip3 install --upgrade pip wheel setuptools
	.venv/bin/pip3 install pylint autopep8 virtualenv pip-tools
	@echo "To activate the venv, execute 'source .venv/bin/activate'"





## MISC -------------------------------

.PHONY: new-service
new-service: ## Bakes a new project from cookiecutter-simcore-pyservice and drops it under services/
	.venv/bin/cookiecutter gh:itisfoundation/cookiecutter-simcore-pyservice --output-dir $(CURDIR)/services

#TODO: does not work in windows
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
setup-check: .env .vscode/settings.json ## checks whether setup is in sync with templates (e.g. vscode settings or .env file)

.PHONY: info
info: ## displays selected parameters of makefile environments
	@echo $(shell make --version | head -1)
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


.PHONY: info-more
info-more: ## displays all parameters of makefile environments
	$(info VARIABLES ------------)
	$(foreach v,                                                                                  \
		$(filter-out $(PREDEFINED_VARIABLES) PREDEFINED_VARIABLES PY_FILES, $(sort $(.VARIABLES))), \
		$(info $(v)=$($(v))     [in $(origin $(v))])                                                \
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
clean: .remove-intermediate-file ## cleans all unversioned files in project
	@git clean -dxf -e .vscode/


.PHONY: reset
reset: ## restart docker daemon
	sudo systemctl restart docker


.PHONY: help
help: ## display all callable targets
	@sort $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf $(if $(IS_WIN),"%-20s %s/n","\033[36m%-20s\033[0m %s\n"), $$1, $$2}'

.DEFAULT_GOAL := help

# author: Sylvain Anderegg

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

SERVICES_LIST := apihub director sidecar storage webserver
CACHED_SERVICES_LIST := ${SERVICES_LIST} webclient
DYNAMIC_SERVICE_FOLDERS_LIST := services/dy-jupyter services/dy-2Dgraph/use-cases services/dy-3dvis services/dy-modeling
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
$(info DOCKER_REGISTRY set to ${DOCKER_REGISTRY})
## Tools ------------------------------------------------------------------------------------------------------
#
tools =

ifeq ($(shell uname -s),Darwin)
	SED = gsed
else
	SED = sed
endif

ifeq ($(shell which ${SED}),)
	tools += $(SED)
endif


## ------------------------------------------------------------------------------------------------------
.PHONY: all
all: help info
ifdef tools
	$(error "Can't find tools:${tools}")
endif


## -------------------------------
# Docker build and composition
.PHONY: build
# target: build: – Builds all core service images.
build: .env .tmp-webclient-build
	${DOCKER_COMPOSE} -f services/docker-compose.yml build --parallel ${SERVICES_LIST};

.PHONY: build-devel .tmp-webclient-build
# target: build-devel, rebuild-devel: – Builds images of core services for development.
build-devel: .env .tmp-webclient-build
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml build --parallel

# TODO: fixes having services_webclient:build present for services_webserver:production when
# targeting services_webserver:development and
.tmp-webclient-build: $(CLIENT_WEB_OUTPUT)
	${DOCKER_COMPOSE} -f services/docker-compose.yml build webclient

# Ensures source-output folder always exists to avoid issues when mounting webclient->webserver dockers. Supports PowerShell
$(CLIENT_WEB_OUTPUT):
ifeq ($(OS), Windows_NT)
	md $(CLIENT_WEB_OUTPUT)
else
	mkdir -p $(CLIENT_WEB_OUTPUT)
endif


.PHONY: build-client rebuild-client
# target: build-client, rebuild-client: – Builds only webclient and webserver images. Use `rebuild` to build w/o cache
build-client: .env
	${DOCKER_COMPOSE} -f services/docker-compose.yml build webclient
	${DOCKER_COMPOSE} -f services/docker-compose.yml build webserver

rebuild-client: .env
	${DOCKER_COMPOSE} -f services/docker-compose.yml build --no-cache webclient
	${DOCKER_COMPOSE} -f services/docker-compose.yml build --no-cache webserver


.PHONY: up up-devel up-swarm up-swarm-devel remove-intermediate-file down down-swarm
# target: up, up-devel: – init swarm and deploys all core and tool services up [-devel suffix uses container in development mode]

docker-swarm-check:
	@if $${DOCKER} node ls > /dev/null 2>&1; then \
		echo "The node is already part of a swarm, running $${DOCKER} swarm leave -f..."; \
		echo "$${DOCKER} swarm leave -f"; \
		$${DOCKER} swarm leave -f; \
	fi;

up: up-swarm
up-devel: up-swarm-devel

up-swarm: .env docker-swarm-check
	${DOCKER} swarm init
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.tools.yml config > $(TEMPCOMPOSE).tmp-compose.yml ;
	${DOCKER} stack deploy -c $(TEMPCOMPOSE).tmp-compose.yml ${SWARM_STACK_NAME}

up-swarm-devel: .env docker-swarm-check $(CLIENT_WEB_OUTPUT)
	${DOCKER} swarm init
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml -f services/docker-compose.tools.yml config > $(TEMPCOMPOSE).tmp-compose.yml
	${DOCKER} stack deploy -c $(TEMPCOMPOSE).tmp-compose.yml ${SWARM_STACK_NAME}

.PHONY: up-webclient-devel
# target: up-webclient-devel: – init swarm and deploys all core and tool services up in development mode. Then it stops the webclient service and starts it again with the watcher attached.
up-webclient-devel: up-swarm-devel remove-intermediate-file
	${DOCKER} service rm services_webclient
	${DOCKER_COMPOSE} -f services/web/client/docker-compose.yml up qx


ifeq ($(WINDOWS_MODE),ON)
remove-intermediate-file:
	$(info    .tmp-compose.yml not removed)
else
remove-intermediate-file:
	rm $(TEMPCOMPOSE).tmp-compose.yml || true
endif

# target: down: – stops `up`
down: down-swarm
down-swarm:
	${DOCKER} swarm leave -f


.PHONY: build-dynamic-services push-dynamic-services
# target: build-dynamic-services: – Builds all dynamic service images (i.e. non-core services)
build-dynamic-services:
ifndef SERVICES_VERSION
	$(error SERVICES_VERSION variable is undefined)
endif
ifndef DOCKER_REGISTRY
	$(error DOCKER_REGISTRY variable is undefined)
endif
	for i in $(DYNAMIC_SERVICE_FOLDERS_LIST); do \
		cd $$i && ${MAKE} build; \
	done

# target: push-dynamic-services: – Builds images from dynamic services (i.e. non-core services) into registry
push-dynamic-services:
ifndef SERVICES_VERSION
	$(error SERVICES_VERSION variable is undefined)
endif
ifndef DOCKER_REGISTRY
	$(error DOCKER_REGISTRY variable is undefined)
endif
	for i in $(DYNAMIC_SERVICE_FOLDERS_LIST); do \
		cd $$i && ${MAKE} push_service_images; \
	done


## -------------------------------
# Cache

.PHONY: pull-cache
pull-cache:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml pull

.PHONY: build-cache
# target: build-cache – Builds service images and tags them as 'cache'
build-cache:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml build --parallel apihub director sidecar storage webclient
	${DOCKER} tag ${DOCKER_REGISTRY}/webclient:cache services_webclient:build
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml build webserver


.PHONY: push-cache
push-cache:
# target: push-cache – Pushes service images tagged as 'cache' into the registry
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml push ${CACHED_SERVICES_LIST}



## -------------------------------
# registry operations
ifdef DOCKER_REGISTRY_NEW
$(info DOCKER_REGISTRY_NEW set to ${DOCKER_REGISTRY_NEW})
endif # DOCKER_REGISTRY_NEW

.PHONY: tag push pull create-stack-file
#target: tag – Tags service images
tag:
ifndef DOCKER_REGISTRY_NEW
	$(error DOCKER_REGISTRY_NEW variable is undefined)
endif
ifndef DOCKER_IMAGE_TAG_NEW
	$(error DOCKER_IMAGE_TAG_NEW variable is undefined)
endif
	@echo "Tagging from ${DOCKER_REGISTRY}, ${DOCKER_IMAGE_TAG} to ${DOCKER_REGISTRY_NEW}, ${DOCKER_IMAGE_TAG_NEW}"
	@for i in $(SERVICES_LIST); do \
		${DOCKER} tag ${DOCKER_REGISTRY}/$$i:${DOCKER_IMAGE_TAG} ${DOCKER_REGISTRY_NEW}/$$i:${DOCKER_IMAGE_TAG_NEW}; \
	done

# target: push – Pushes images into a registry
push:
	${DOCKER_COMPOSE} -f services/docker-compose.yml push ${SERVICES_LIST}

# target: pull – Pulls images from a registry
pull:
	${DOCKER_COMPOSE} -f services/docker-compose.yml pull ${SERVICES_LIST}

# target: create-stack-file – use as 'make create-stack-file output_file=stack.yaml'
create-stack-file:
	${DOCKER_COMPOSE} -f services/docker-compose.yml config > $(output_file)

## -------------------------------
# Tools

.PHONY: info
# target: info – Displays some parameters of makefile environments
info:
	@echo '+ VCS_* '
	@echo '  - ULR                : ${VCS_URL}'
	@echo '  - REF                : ${VCS_REF}'
	@echo '  - (STATUS)REF_CLIENT : (${VCS_STATUS_CLIENT}) ${VCS_REF_CLIENT}'
	@echo '+ BUILD_DATE           : ${BUILD_DATE}'
	@echo '+ VERSION              : ${VERSION}'
	@echo '+ WINDOWS_MODE         : ${WINDOWS_MODE}'
	@echo '+ DOCKER_REGISTRY      : ${DOCKER_REGISTRY}'
	@echo '+ DOCKER_IMAGE_TAG     : ${DOCKER_IMAGE_TAG}'
	@echo '+ SERVICES_VERSION     : ${SERVICES_VERSION}'
	@echo '+ PY_FILES             : $(shell echo $(PY_FILES) | wc -w) files'


.PHONY: pylint
# target: pylint – Runs python linter framework's wide
pylint:
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes
	/bin/bash -c "pylint --rcfile=.pylintrc $(PY_FILES)"


.PHONY: new-service
# target: new-service – Bakes a new project from cookiecutter-simcore-pyservice and drops it under services/
new-service:
	.venv/bin/cookiecutter gh:itisfoundation/cookiecutter-simcore-pyservice --output-dir $(CURDIR)/services


## -------------------------------
# Virtual Environments

.env: .env-devel
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
# target: setup-check – Checks whether setup is in sync with templates (e.g. vscode settings or .env file)
setup-check: .env .vscode/settings.json

.venv:
# target: .venv – Creates a python virtual environment with dev tools (pip, pylint, ...)
	python3 -m venv .venv
	.venv/bin/pip3 install --upgrade pip wheel setuptools
	.venv/bin/pip3 install pylint autopep8 virtualenv pip-tools
	@echo "To activate the venv, execute 'source .venv/bin/activate' or '.venv/Scripts/activate.bat' (WIN)"

.venv27: .venv
# target: .venv27 – Creates a python2.7 virtual environment with dev tools
	@python2 --version
	.venv/bin/virtualenv --python=python2 .venv27
	@echo "To activate the venv27, execute 'source .venv27/bin/activate' or '.venv27/Scripts/activate.bat' (WIN)"


.PHONY: requirements
# target: requirements – Compiles ALL PiP requirements (.in->.txt) WARNING: UNDER DEVELOPMENT!!
requirements:
	pushd packages/s3wrapper/requirements && $(MAKE) -f Makefile all && popd
	pushd packages/service-library/requirements && $(MAKE) -f Makefile all && popd
	pushd packages/simcore-sdk/requirements && $(MAKE) -f Makefile all && popd
	pushd services/web/server/requirements && $(MAKE) -f Makefile all && popd
	pushd services/storage/requirements && $(MAKE) -f Makefile all && popd
	pushd services/sidecar/requirements && $(MAKE) -f Makefile all && popd
	pushd services/director/requirements && $(MAKE) -f Makefile all && popd


## -------------------------------
# Auxiliary targets.

.PHONY: clean
# target: clean – Cleans all unversioned files in project
clean: remove-intermediate-file
	@git clean -dxf -e .vscode/


.PHONY: help
# target: help – Display all callable targets
help:
	@echo "Make targets in osparc-simcore:"
	@echo
	@egrep "^\s*#\s*target\s*:\s*" [Mm]akefile \
	| $(SED) -r "s/^\s*#\s*target\s*:\s*//g"
	@echo

# author: Sylvain Anderegg

# TODO: add flavours by combinging docker-compose files. Namely development, test and production.
VERSION := $(shell uname -a)

# SAN this is a hack so that docker-compose works in the linux virtual environment under Windows
WINDOWS_MODE=OFF
ifneq (,$(findstring Microsoft,$(VERSION)))
$(info    detected WSL)
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
export RUN_DOCKER_ENGINE_ROOT=1
# Windows does not have these things defined... but they are needed to execute a local swarm
export DOCKER_GID=1042
export HOST_GID=1000
WINDOWS_MODE=ON
else ifeq ($(OS), Windows_NT)
$(info    detected Powershell/CMD)
export DOCKER_COMPOSE=docker-compose.exe
export DOCKER=docker.exe
export RUN_DOCKER_ENGINE_ROOT=1
export DOCKER_GID=1042
export HOST_GID=1000
WINDOWS_MODE=ON
else ifneq (,$(findstring Darwin,$(VERSION)))
$(info    detected OSX)
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
export RUN_DOCKER_ENGINE_ROOT=1
export DOCKER_GID=1042
export HOST_GID=1000
else
$(info    detected native linux)
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
export RUN_DOCKER_ENGINE_ROOT=0
export DOCKER_GID=1042
export HOST_GID=1000
# TODO: Add a meaningfull call to retrieve the local docker group ID and the user ID in linux.
endif


PY_FILES = $(strip $(shell find services packages -iname '*.py' -not -path "*egg*" -not -path "*contrib*" -not -path "*-sdk/python*" -not -path "*generated_code*" -not -path "*datcore.py" -not -path "*web/server*"))

TEMPCOMPOSE := $(shell mktemp)

SERVICES_LIST := apihub director sidecar storage webserver
CACHED_SERVICES_LIST := ${SERVICES_LIST} webclient
DYNAMIC_SERVICE_FOLDERS_LIST := services/dy-jupyter services/dy-2Dgraph/use-cases services/dy-3dvis services/dy-modeling

VCS_REF:=$(shell git rev-parse --short HEAD)
VCS_REF_CLIENT:=$(shell git log --pretty=tformat:"%h" -n1 services/web/client)
BUILD_DATE:=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

export VCS_REF
export VCS_REF_CLIENT
export BUILD_DATE
export SERVICES_VERSION=2.8.0
export DOCKER_REGISTRY=masu.speag.com


## Tools
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
all: help
ifdef tools
	$(error "Can't find tools:${tools}")
endif


## -------------------------------
# Framework services build and composition

.PHONY: build-devel
# target: build-devel: – Builds images of core services for development
build-devel: .env pull-cache
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml build

.PHONY: rebuild-devel
# target: rebuild-devel: – As build-devel but w/o cache
rebuild-devel:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml build --no-cache

.PHONY: up-devel
# target: up-devel: – Start containers of core services in development mode
up-devel:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml -f services/docker-compose.tools.yml up

up-webclient-devel: up-swarm-devel remove-intermediate-file file-watcher
	${DOCKER} service rm services_webclient
	${DOCKER_COMPOSE} -f services/web/client/docker-compose.yml up qx

rebuild-webclient-devel-solo:
	${DOCKER_COMPOSE} -f services/web/client/docker-compose.yml build --no-cache qx

up-webclient-devel-solo:
	${DOCKER_COMPOSE} -f services/web/client/docker-compose.yml up qx

.PHONY: build
# target: build: – Builds images for production
build: .env pull-cache
	${DOCKER_COMPOSE} -f services/docker-compose.yml build

build-client: pull-cache
	${DOCKER_COMPOSE} -f services/docker-compose.yml build webclient
	${DOCKER_COMPOSE} -f services/docker-compose.yml build webserver

rebuild-client:
	${DOCKER_COMPOSE} -f services/docker-compose.yml build --no-cache webclient
	${DOCKER_COMPOSE} -f services/docker-compose.yml build --no-cache webserver

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

push_dynamic_services:
ifndef SERVICES_VERSION
	$(error SERVICES_VERSION variable is undefined)
endif
ifndef DOCKER_REGISTRY
	$(error DOCKER_REGISTRY variable is undefined)
endif
	for i in $(DYNAMIC_SERVICE_FOLDERS_LIST); do \
		cd $$i && ${MAKE} push_service_images; \
	done

rebuild:
	${DOCKER_COMPOSE} -f services/docker-compose.yml build --no-cache

up:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.tools.yml up

up-swarm:
	${DOCKER} swarm init
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.tools.yml config > $(TEMPCOMPOSE).tmp-compose.yml ;
	${DOCKER} stack deploy -c $(TEMPCOMPOSE).tmp-compose.yml services

up-swarm-devel:
	${DOCKER} swarm init
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml -f services/docker-compose.tools.yml config > $(TEMPCOMPOSE).tmp-compose.yml
	${DOCKER} stack deploy -c $(TEMPCOMPOSE).tmp-compose.yml services

ifeq ($(WINDOWS_MODE),ON)
remove-intermediate-file:
	$(info    .tmp-compose.yml not removed)
else
remove-intermediate-file:
	rm $(TEMPCOMPOSE).tmp-compose.yml
endif

ifeq ($(WINDOWS_MODE),ON)
file-watcher:
	pip install docker-windows-volume-watcher
	# unfortunately this is not working properly at the moment
	# docker-windows-volume-watcher python package will be installed but not executed
	# you will have to run 'docker-volume-watcher *qx*' in a different process in ./services/web/client/source
	# docker-volume-watcher &
else
file-watcher:
	true
endif

down:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.tools.yml down
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml down

down-swarm:
	${DOCKER} swarm leave -f

PLATFORM_VERSION=3.38
DOCKER_REGISTRY=masu.speag.com
#DOCKER_REGISTRY=registry.osparc.io


push_platform_images:
	${DOCKER} login ${DOCKER_REGISTRY}
	for i in $(SERVICES_LIST); do \
		${DOCKER} tag services_$$i:latest ${DOCKER_REGISTRY}/simcore/workbench/$$i:${PLATFORM_VERSION}; \
		${DOCKER} push ${DOCKER_REGISTRY}/simcore/workbench/$$i:${PLATFORM_VERSION}; \
	done

  setup-check: .env .vscode/settings.json

push_client_image:
	${DOCKER} login ${DOCKER_REGISTRY}
	${DOCKER} tag services_webserver:latest ${DOCKER_REGISTRY}/simcore/workbench/webserver:${PLATFORM_VERSION}
	${DOCKER} push ${DOCKER_REGISTRY}./simcore/workbench/webserver:${PLATFORM_VERSION}

## -------------------------------
# Virtual Environments

.env: .env-devel
	# first check if file exists, copies it
	if [ ! -f $@ ]	; then \
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

.venv:
	python3 -m venv .venv
	.venv/bin/pip3 install --upgrade pip wheel setuptools
	.venv/bin/pip3 install pylint autopep8 virtualenv
	@echo "To activate the venv, execute 'source .venv/bin/activate' or '.venv/bin/activate.bat' (WIN)"

.venv27: .venv
	@python2 --version
	.venv/bin/virtualenv --python=python2 .venv27
	@echo "To activate the venv27, execute 'source .venv27/bin/activate' or '.venv27/bin/activate.bat' (WIN)"

.PHONY: info
# target: info – Displays some parameters of makefile environments
info:
	@echo '+ vcs ref '
	@echo '  - all       : ${VCS_REF}'
	@echo '  - web/client: ${VCS_REF_CLIENT}'
	@echo '+ date        : ${BUILD_DATE}'


.PHONY: pylint
# target: pylint – Runs python linter framework's wide
pylint:
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes
	/bin/bash -c "pylint --rcfile=.pylintrc $(PY_FILES)"


.PHONY: new-service
# target: new-service – Bakes a new service from cookiecutter-simcore-pyservice and creates it under services/
new-service:
	.venv/bin/cookiecutter gh:itisfoundation/cookiecutter-simcore-pyservice --output-dir $(CURDIR)/services

# cache ------------------------------------------------------------------------------------
.PHONY: pull-cache
pull-cache:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml pull --ignore-pull-failures

.PHONY: build-cache	
build-cache: pull-cache	
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml build --parallel apihub director sidecar storage webclient
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml build webserver

.PHONY: push-cache	
push-cache:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml push ${CACHED_SERVICES_LIST}


# staging ----------------
.PHONY: build-staging
build-staging:
	export DOCKER_IMAGE_PREFIX=itisfoundation/; \
	export DOCKER_IMAGE_TAG=staging-latest; \
	${MAKE} build

TRAVIS_PLATFORM_STAGE_VERSION := staging-$(shell date +"%Y-%m-%d").${TRAVIS_BUILD_NUMBER}.$(shell git rev-parse HEAD)
.PHONY: push-staging
push-staging:
	export DOCKER_IMAGE_PREFIX=itisfoundation/ \
	export DOCKER_IMAGE_TAG=staging-latest \
	# pushes the staging-latest images
	${DOCKER_COMPOSE} -f services/docker-compose.yml push ${SERVICES_LIST}
	# pushes the staging-versioned images
	for i in $(SERVICES_LIST); do \
		${DOCKER} tag services_$$i:staging-latest itisfoundation/$$i:${TRAVIS_PLATFORM_STAGE_VERSION}; \
		${DOCKER} push itisfoundation/$$i:${TRAVIS_PLATFORM_STAGE_VERSION}; \
	done

.PHONY: pull-staging	
pull-staging:
	export DOCKER_IMAGE_PREFIX=itisfoundation/; \
	export DOCKER_IMAGE_TAG=staging-latest; \
	${DOCKER_COMPOSE} -f services/docker-compose.yml pull

.PHONY: create-staging-stack-file
create-staging-stack-file:
	# Usage: make creat-staging-stack-file output_file=stack.yaml
	export DOCKER_IMAGE_PREFIX=itisfoundation/; \
	export DOCKER_IMAGE_TAG=staging-latest; \
	${DOCKER_COMPOSE} -f services/docker-compose.yml config > $(output_file)


## -------------------------------
# Auxiliary targets.

.PHONY: clean
# target: clean – Cleans all unversioned files in project
clean:
	@git clean -dxf -e .vscode/


.PHONY: help
# target: help – Display all callable targets
help:
	@echo
	@egrep "^\s*#\s*target\s*:\s*" [Mm]akefile \
	| $(SED) -r "s/^\s*#\s*target\s*:\s*//g"
	@echo

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

SERVICES_LIST = apihub director sidecar storage webserver
CACHED_SERVICES_LIST = ${SERVICES_LIST} webclient
DYNAMIC_SERVICE_FOLDERS_LIST = services/dy-jupyter services/dy-2Dgraph/use-cases services/dy-3dvis services/dy-modeling

export SERVICES_VERSION=2.8.0
export DOCKER_REGISTRY=masu.speag.com

VCS_REF:=$(shell git rev-parse --short HEAD)
VCS_REF_CLIENT:=$(shell git log --pretty=tformat:"%h" -n1 services/web/client)
BUILD_DATE:=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

export VCS_REF
export VCS_REF_CLIENT
export BUILD_DATE

info:
	@echo '+ vcs ref '
	@echo '  - all       : ${VCS_REF}'
	@echo '  - web/client: ${VCS_REF_CLIENT}'
	@echo '+ date        : ${BUILD_DATE}'

all:
	@echo 'run `make build-devel` to build your dev environment'
	@echo 'run `make up-devel` to start your dev environment.'
	@echo 'see Makefile for further targets'

clean:
	@git clean -dxf -e .vscode/

build-devel: pull-cache
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml build

rebuild-devel:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml build --no-cache

up-devel:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml -f services/docker-compose.tools.yml up

up-webclient-devel: up-swarm-devel remove-intermediate-file file-watcher
	${DOCKER} service rm services_webclient
	${DOCKER_COMPOSE} -f services/web/client/docker-compose.yml up qx

rebuild-webclient-devel-solo:
	${DOCKER_COMPOSE} -f services/web/client/docker-compose.yml build --no-cache qx

up-webclient-devel-solo:
	${DOCKER_COMPOSE} -f services/web/client/docker-compose.yml up qx


build: pull-cache
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

pylint:
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes
	/bin/bash -c "pylint --rcfile=.pylintrc $(PY_FILES)"


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

.env: .env-devel
	$(info #####  $< is newer than $@ ####)
	@diff -uN $@ $<
	@false

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


# ----------TRAVIS ------------------------------------------------------------------------------------
pull-cache:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml pull --ignore-pull-failures
	
build-cache: pull-cache	
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml build --parallel apihub director sidecar storage webclient
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml build webserver

push-cache:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml push ${CACHED_SERVICES_LIST}


# staging ----------------
build-staging:
	export DOCKER_IMAGE_PREFIX=itisfoundation/; \
	export DOCKER_IMAGE_TAG=staging-latest; \
	${MAKE} build

TRAVIS_PLATFORM_STAGE_VERSION=staging-$(shell date +"%Y-%m-%d").${TRAVIS_BUILD_NUMBER}.$(shell git rev-parse HEAD)
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
	
pull-staging:
	export DOCKER_IMAGE_PREFIX=itisfoundation/; \
	export DOCKER_IMAGE_TAG=staging-latest; \
	${DOCKER_COMPOSE} -f services/docker-compose.yml pull

create-staging-stack-file:
	# Usage: make creat-staging-stack-file output_file=stack.yaml
	export DOCKER_IMAGE_PREFIX=itisfoundation/; \
	export DOCKER_IMAGE_TAG=staging-latest; \
	${DOCKER_COMPOSE} -f services/docker-compose.yml config > $(output_file)

.PHONY: all clean build-devel rebuild-devel up-devel build up down test after_test push_platform_images file-watcher up-webclient-devel

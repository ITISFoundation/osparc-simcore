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
build-devel:
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
build:
	${DOCKER_COMPOSE} -f services/docker-compose.yml build

build-client:
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
	cd services/dy-jupyter && ${MAKE} build
	cd services/dy-2Dgraph/use-cases && ${MAKE} build
	cd services/dy-3dvis && ${MAKE} build
	cd services/dy-modeling && ${MAKE} build

push_dynamic_services:
ifndef SERVICES_VERSION
	$(error SERVICES_VERSION variable is undefined)
endif
ifndef DOCKER_REGISTRY
	$(error DOCKER_REGISTRY variable is undefined)
endif
	cd services/dy-jupyter && ${MAKE} push_service_images
	cd services/dy-2Dgraph/use-cases && ${MAKE} push_service_images
	cd services/dy-3dvis && ${MAKE} push_service_images
	cd services/dy-modeling && ${MAKE} push_service_images

rebuild:
	${DOCKER_COMPOSE} -f services/docker-compose.yml build --no-cache

up:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.tools.yml up

up-swarm:
	${DOCKER} swarm init
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.deploy.yml -f services/docker-compose.tools.yml config > $(TEMPCOMPOSE).tmp-compose.yml ;
	${DOCKER} stack deploy -c $(TEMPCOMPOSE).tmp-compose.yml services

up-swarm-devel:
	${DOCKER} swarm init
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml -f services/docker-compose.deploy.devel.yml -f services/docker-compose.tools.yml config > $(TEMPCOMPOSE).tmp-compose.yml
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

stack-up:
	${DOCKER} swarm init

stack-down:
	${DOCKER} stack rm osparc
	${DOCKER} swarm leave -f

deploy:
	${DOCKER} stack deploy -c services/docker-compose.swarm.yml services --with-registry-auth


PLATFORM_VERSION=3.38
DOCKER_REGISTRY=masu.speag.com
#DOCKER_REGISTRY=registry.osparc.io


push_platform_images:
	${DOCKER} login ${DOCKER_REGISTRY}
	${DOCKER} tag services_apihub:latest ${DOCKER_REGISTRY}/simcore/workbench/apihub:${PLATFORM_VERSION}
	${DOCKER} push ${DOCKER_REGISTRY}/simcore/workbench/apihub:${PLATFORM_VERSION}
	${DOCKER} tag services_webserver:latest ${DOCKER_REGISTRY}/simcore/workbench/webserver:${PLATFORM_VERSION}
	${DOCKER} push ${DOCKER_REGISTRY}/simcore/workbench/webserver:${PLATFORM_VERSION}
	${DOCKER} tag services_sidecar:latest ${DOCKER_REGISTRY}/simcore/workbench/sidecar:${PLATFORM_VERSION}
	${DOCKER} push ${DOCKER_REGISTRY}/simcore/workbench/sidecar:${PLATFORM_VERSION}
	${DOCKER} tag services_director:latest ${DOCKER_REGISTRY}/simcore/workbench/director:${PLATFORM_VERSION}
	${DOCKER} push ${DOCKER_REGISTRY}/simcore/workbench/director:${PLATFORM_VERSION}
	${DOCKER} tag services_storage:latest ${DOCKER_REGISTRY}/simcore/workbench/storage:${PLATFORM_VERSION}
	${DOCKER} push ${DOCKER_REGISTRY}/simcore/workbench/storage:${PLATFORM_VERSION}

  setup-check: .env .vscode/settings.json

push_client_image:
	${DOCKER} login ${DOCKER_REGISTRY}
	${DOCKER} tag services_webserver:latest ${DOCKER_REGISTRY}/simcore/workbench/webserver:${PLATFORM_VERSION}
	${DOCKER} push ${DOCKER_REGISTRY}./simcore/workbench/webserver:${PLATFORM_VERSION}

## -------------------------------
# Virtual Environments

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


## -------------------------------
# Travis targets

travis-pull-cache-images:
	${DOCKER} pull itisfoundation/apihub:cache || true
	${DOCKER} pull itisfoundation/director:cache || true
	${DOCKER} pull itisfoundation/sidecar:cache || true
	${DOCKER} pull itisfoundation/storage:cache || true
	${DOCKER} pull itisfoundation/webclient:cache || true
	${DOCKER} pull itisfoundation/webserver:cache || true

travis-build:
	#TODO: preferably there should be only one build script. the problem is the --parallel flag and the webclient/webserver docker that is multistage in 2 files
	# it should be ideally only docker-compose build --parallel
	${MAKE} travis-pull-cache-images
	${DOCKER_COMPOSE} -f services/docker-compose.yml build --parallel apihub director sidecar storage webclient
	${DOCKER_COMPOSE} -f services/docker-compose.yml build webserver

travis-build-cache-images:
	${MAKE} travis-pull-cache-images
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml build --parallel apihub director sidecar storage webclient
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.cache.yml build webserver

travis-push-cache-images:
	${DOCKER} tag services_apihub:latest itisfoundation/apihub:cache
	${DOCKER} tag services_webserver:latest itisfoundation/webserver:cache
	${DOCKER} tag services_sidecar:latest itisfoundation/sidecar:cache
	${DOCKER} tag services_director:latest itisfoundation/director:cache
	${DOCKER} tag services_storage:latest itisfoundation/storage:cache
	${DOCKER} tag services_webclient:build itisfoundation/webclient:cache
	${DOCKER} tag services_webserver:latest itisfoundation/webserver:cache

	${DOCKER} push itisfoundation/apihub:cache
	${DOCKER} push itisfoundation/director:cache
	${DOCKER} push itisfoundation/sidecar:cache
	${DOCKER} push itisfoundation/storage:cache
	${DOCKER} push itisfoundation/webclient:cache
	${DOCKER} push itisfoundation/webserver:cache

TRAVIS_PLATFORM_STAGE_VERSION=staging-$(shell date +"%Y-%m-%d").${TRAVIS_BUILD_NUMBER}.$(shell git rev-parse HEAD)
TRAVIS_PLATFORM_STAGE_LATEST=staging-latest
travis-push-staging-images:
	${DOCKER} tag services_apihub:latest itisfoundation/apihub:${TRAVIS_PLATFORM_STAGE_VERSION}
	${DOCKER} tag services_webserver:latest itisfoundation/webserver:${TRAVIS_PLATFORM_STAGE_VERSION}
	${DOCKER} tag services_sidecar:latest itisfoundation/sidecar:${TRAVIS_PLATFORM_STAGE_VERSION}
	${DOCKER} tag services_director:latest itisfoundation/director:${TRAVIS_PLATFORM_STAGE_VERSION}
	${DOCKER} tag services_storage:latest itisfoundation/storage:${TRAVIS_PLATFORM_STAGE_VERSION}
	${DOCKER} tag services_apihub:latest itisfoundation/apihub:${TRAVIS_PLATFORM_STAGE_LATEST}
	${DOCKER} tag services_webserver:latest itisfoundation/webserver:${TRAVIS_PLATFORM_STAGE_LATEST}
	${DOCKER} tag services_sidecar:latest itisfoundation/sidecar:${TRAVIS_PLATFORM_STAGE_LATEST}
	${DOCKER} tag services_director:latest itisfoundation/director:${TRAVIS_PLATFORM_STAGE_LATEST}
	${DOCKER} tag services_storage:latest itisfoundation/storage:${TRAVIS_PLATFORM_STAGE_LATEST}
	${DOCKER} push itisfoundation/apihub:${TRAVIS_PLATFORM_STAGE_VERSION}
	${DOCKER} push itisfoundation/webserver:${TRAVIS_PLATFORM_STAGE_VERSION}
	${DOCKER} push itisfoundation/sidecar:${TRAVIS_PLATFORM_STAGE_VERSION}
	${DOCKER} push itisfoundation/director:${TRAVIS_PLATFORM_STAGE_VERSION}
	${DOCKER} push itisfoundation/storage:${TRAVIS_PLATFORM_STAGE_VERSION}
	${DOCKER} push itisfoundation/apihub:${TRAVIS_PLATFORM_STAGE_LATEST}
	${DOCKER} push itisfoundation/webserver:${TRAVIS_PLATFORM_STAGE_LATEST}
	${DOCKER} push itisfoundation/sidecar:${TRAVIS_PLATFORM_STAGE_LATEST}
	${DOCKER} push itisfoundation/director:${TRAVIS_PLATFORM_STAGE_LATEST}
	${DOCKER} push itisfoundation/storage:${TRAVIS_PLATFORM_STAGE_LATEST}


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

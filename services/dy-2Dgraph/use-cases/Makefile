VERSION := $(shell cat /proc/version)
# SAN this is a hack so that docker-compose works in the linux virtual environment under Windows
ifneq (,$(findstring Microsoft,$(VERSION)))
# executing from bash
$(echo 'detected WSL')
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
else ifeq ($(OS), Windows_NT)
$(echo 'detected Powershell/CMD')
# executing from powershell
export DOCKER_COMPOSE=docker-compose.exe
export DOCKER=docker.exe
else
$(echo 'detected native linux')
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
endif

DEFAULT_SERVICES_VERSION := 1.8.0
DEFAULT_DOCKER_REGISTRY := masu.speag.com
ifndef SERVICES_VERSION
export SERVICES_VERSION = $(DEFAULT_SERVICES_VERSION)
endif
ifndef DOCKER_REGISTRY
export DOCKER_REGISTRY = ${DEFAULT_DOCKER_REGISTRY}
endif

export VCS_URL:=$(shell git config --get remote.origin.url)
export VCS_REF:=$(shell git rev-parse --short HEAD)
export BUILD_DATE:=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
export BASE_IMAGE:=masu.speag.com/simcore/services/dynamic/jupyter-base-notebook:${SERVICES_VERSION}

PY_FILES := $(strip $(shell find . -iname '*.py'))

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

.PHONY: all
all: help info
ifdef tools
	$(error "Can't find tools:${tools}")
endif

.PHONY: build rebuild
# target: build, rebuild: – Builds all service images. Use `rebuild` to build w/o cache.
build: .check-env
	${DOCKER_COMPOSE} -f docker-compose.yml build --parallel

rebuild: .check-env
	${DOCKER_COMPOSE} -f docker-compose.yml build --no-cache --parallel

.PHONY: build-devel rebuild-devel
# target: build-devel: – Builds images of core services for development. Use 'rebuild-devel' to build w/o cache.
build-devel: .check-env
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build --parallel

rebuild-devel: .check-env
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build --no-cache --parallel

.PHONY: up up-devel down
# target: up, down: – starts/stops service
# target: up-devel: – deploys service in devel mode together with minimal swarm-like environment
up:
	${DOCKER_COMPOSE} -f docker-compose.yml up

up-devel:
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml up

down:
	${DOCKER_COMPOSE} -f docker-compose.yml down
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml down

.PHONY: push_service_images
# target: push_service_images – Pushes the the service images to ${DOCKER_REGISTRY}
push_service_images: .check-env
	${DOCKER} login ${DOCKER_REGISTRY}
	${DOCKER_COMPOSE} -f docker-compose.yml push

## -------------------------------
# Tools

.PHONY: info
# target: info – Displays some parameters of makefile environments
info: .check-env
	@echo '+ VCS_* '
	@echo '  - URL                : ${VCS_URL}'
	@echo '  - REF                : ${VCS_REF}'
	@echo '+ BUILD_DATE           : ${BUILD_DATE}'
	@echo '+ VERSION              : ${VERSION}'
	@echo '+ DOCKER_REGISTRY      : ${DOCKER_REGISTRY}'
	@echo '+ SERVICES_VERSION     : ${SERVICES_VERSION}'
	@echo '+ PY_FILES             : $(shell echo $(PY_FILES) | wc -w) files'

## -------------------------------
# Virtual Environments
PHONY: .check-env
.check-env: .env
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

.venv:
# target: .venv – Creates a python virtual environment with dev tools (pip, pylint, ...)
	python3 -m venv .venv
	.venv/bin/pip3 install --upgrade pip wheel setuptools
	.venv/bin/pip3 install pylint autopep8 virtualenv
	@echo "To activate the venv, execute 'source .venv/bin/activate' or '.venv/bin/activate.bat' (WIN)"

## -------------------------------
# Auxiliary targets.

.PHONY: clean
# target: clean – Cleans all unversioned files in project
clean:
	@git clean -dxf -e .vscode/


.PHONY: help
# target: help – Display all callable targets
help:
	@echo "Make targets in osparc-simcore:"
	@echo
	@egrep "^\s*#\s*target\s*:\s*" [Mm]akefile \
	| $(SED) -r "s/^\s*#\s*target\s*:\s*//g"
	@echo

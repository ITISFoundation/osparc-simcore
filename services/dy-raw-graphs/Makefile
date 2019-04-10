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


DEFAULT_SERVICES_VERSION=2.8.0
DEFAULT_DOCKER_REGISTRY=masu.speag.com
export VCS_REF=$(shell git rev-parse --short HEAD)
export BUILD_DATE=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
export SERVICE_BASE_PATH=simcore/services/dynamic/raw-graphs
export SERVICE_BASE_PATH_TABLE=simcore/services/dynamic/raw-graphs-table

all:
	@echo 'run `make build` to build'
	@echo 'run `make up` to start'
	@echo 'see Makefile for further targets'

check-env:
ifndef SERVICES_VERSION
	$(warning SERVICES_VERSION variable is undefined, using default ${DEFAULT_SERVICES_VERSION})
	export SERVICES_VERSION=${DEFAULT_SERVICES_VERSION}
endif
ifndef DOCKER_REGISTRY
	$(warning DOCKER_REGISTRY variable is undefined, using default ${DEFAULT_DOCKER_REGISTRY})
	export DOCKER_REGISTRY=${DEFAULT_DOCKER_REGISTRY}
endif

build: check-env
	${DOCKER_COMPOSE} -f docker-compose.yml build

rebuild: check-env
	${DOCKER_COMPOSE} -f docker-compose.yml build --no-cache

up: down
	${DOCKER_COMPOSE} -f docker-compose.yml up

build-devel: check-env
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build

rebuild-devel: check-env
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build --no-cache

up-devel: down
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml up

down:
	${DOCKER_COMPOSE} -f docker-compose.yml down
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml down

push_service_images: check-env
	${DOCKER} login ${DOCKER_REGISTRY}
	${DOCKER} push ${DOCKER_REGISTRY}/${SERVICE_BASE_PATH}:${SERVICES_VERSION}
	${DOCKER} push ${DOCKER_REGISTRY}/${SERVICE_BASE_PATH_TABLE}:${SERVICES_VERSION}

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



#export SERVICES_VERSION=1.7.0
export VCS_REF=$(shell git rev-parse --short HEAD)
export BUILD_DATE=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

# DOCKER_REGISTRY=masu.speag.com
#DOCKER_REGISTRY=registry.osparc.io
export SERVICE_BASE_PATH=simcore/services/dynamic/jupyter-base-notebook
export SERVICE_SCIPY_PATH=simcore/services/dynamic/jupyter-scipy-notebook

all:
	@echo 'run `make build` to build'
	@echo 'run `make up` to start'
	@echo 'see Makefile for further targets'

check-env:
ifndef SERVICES_VERSION
	$(error SERVICES_VERSION variable is undefined)
endif
ifndef DOCKER_REGISTRY
	$(error DOCKER_REGISTRY variable is undefined)
endif

build: check-env
	${DOCKER_COMPOSE} -f docker-compose.yml build

build-devel: check-env
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build

rebuild: check-env
	${DOCKER_COMPOSE} -f docker-compose.yml build --no-cache

up:
	${DOCKER_COMPOSE} -f docker-compose.yml up

up-devel:
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml up

down:
	${DOCKER_COMPOSE} -f docker-compose.yml down
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml down

push_service_images: check-env
	${DOCKER} login ${DOCKER_REGISTRY}
	${DOCKER} push ${DOCKER_REGISTRY}/${SERVICE_BASE_PATH}:${SERVICES_VERSION}
	${DOCKER} push ${DOCKER_REGISTRY}/${SERVICE_SCIPY_PATH}:${SERVICES_VERSION}

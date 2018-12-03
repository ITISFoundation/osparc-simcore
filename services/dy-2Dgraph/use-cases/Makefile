VERSION := $(shell cat /proc/version)
# SAN this is a hack so that docker-compose works in the linux virtual environment under Windows
ifneq (,$(findstring Microsoft,$(VERSION)))
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
else
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
endif

# export SERVICES_VERSION=1.2.0
export VCS_REF=$(shell git rev-parse --short HEAD) 
export BUILD_DATE=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
export BASE_IMAGE=masu.speag.com/simcore/services/dynamic/jupyter-base-notebook:${SERVICES_VERSION}
# export SERVICE_PATH=simcore/services/dynamic/3d-viewer
all:
	@echo 'run `make build-devel` to build your dev environment'
	@echo 'run `make up-devel` to start your dev environment.'
	@echo 'see Makefile for further targets'

check-env:
ifndef SERVICES_VERSION
	$(error SERVICES_VERSION variable is undefined)
endif
ifndef DOCKER_REGISTRY
	$(error DOCKER_REGISTRY variable is undefined)
endif
	
build-devel: check-env
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build

rebuild-devel: check-env
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build --no-cache

up-devel:
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml up

build: check-env
	${DOCKER_COMPOSE} -f docker-compose.yml build

rebuild: check-env
	${DOCKER_COMPOSE} -f docker-compose.yml build --no-cache

up:
	${DOCKER_COMPOSE} -f docker-compose.yml up

down:
	${DOCKER_COMPOSE} -f docker-compose.yml down
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml down

push_service_images: check-env
	${DOCKER} login ${DOCKER_REGISTRY}
	${DOCKER} push ${DOCKER_REGISTRY}/simcore/services/dynamic/cc-0d-viewer:${SERVICES_VERSION}
	${DOCKER} push ${DOCKER_REGISTRY}/simcore/services/dynamic/cc-1d-viewer:${SERVICES_VERSION}
	${DOCKER} push ${DOCKER_REGISTRY}/simcore/services/dynamic/cc-2d-viewer:${SERVICES_VERSION}
	${DOCKER} push ${DOCKER_REGISTRY}/simcore/services/dynamic/kember-viewer:${SERVICES_VERSION}
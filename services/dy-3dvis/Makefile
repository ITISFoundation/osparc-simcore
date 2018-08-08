VERSION := $(shell cat /proc/version)
# SAN this is a hack so that docker-compose works in the linux virtual environment under Windows
ifneq (,$(findstring Microsoft,$(VERSION)))
export DOCKER_COMPOSE=docker-compose.exe
export DOCKER=docker.exe
else
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
endif

all:
	@echo 'run `make build-devel` to build your dev environment'
	@echo 'run `make up-devel` to start your dev environment.'
	@echo 'see Makefile for further targets'

build:	
	${DOCKER_COMPOSE} -f docker-compose.yml build --build-arg VCS_REF=`git rev-parse --short HEAD` --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"`

rebuild:
	${DOCKER_COMPOSE} -f docker-compose.yml build --no-cache --build-arg VCS_REF=`git rev-parse --short HEAD` --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"`

build-devel: .env
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build --build-arg VCS_REF=`git rev-parse --short HEAD` --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"`

rebuild-devel:
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build --no-cache --build-arg VCS_REF=`git rev-parse --short HEAD` --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"`

up:
	${DOCKER_COMPOSE} -f docker-compose.yml up

up-devel:
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml up

down:
	${DOCKER_COMPOSE} -f docker-compose.yml down

down-devel:
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml down

SERVICES_VERSION=1.0
SERVICE_NAME=masu.speag.com/simcore/services/dynamic/3d-viewer

push_service_images:
	${DOCKER} login masu.speag.com
	${DOCKER} tag dy-3dvis_simcore-paraviewweb:latest ${SERVICE_NAME}:${SERVICES_VERSION}
	${DOCKER} push ${SERVICE_NAME}:${SERVICES_VERSION}

.env: .env-devel
	$(info #####  $< is newer than $@ ####)
	@diff -uN $@ $<
	@false
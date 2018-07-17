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

build-devel: .env
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build --build-arg VCS_REF=`git rev-parse --short HEAD` --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"`

up:
	${DOCKER_COMPOSE} -f docker-compose.yml up

up-devel:
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml up

down:
	${DOCKER_COMPOSE} -f docker-compose.yml down

down-devel:
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml down

SERVICES_VERSION=1.0

push_service_images:
	${DOCKER} login masu.speag.com
	${DOCKER} tag use-cases_cc-0d:latest masu.speag.com/simcore/services/dynamic/cc-0d-viewer:${SERVICES_VERSION}
	${DOCKER} push masu.speag.com/simcore/services/dynamic/cc-0d-viewer:${SERVICES_VERSION}

.env: .env-devel
	$(info #####  $< is newer than $@ ####)
	@diff -uN $@ $<
	@false
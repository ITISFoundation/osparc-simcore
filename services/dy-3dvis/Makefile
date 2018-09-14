VERSION := $(shell cat /proc/version)
# SAN this is a hack so that docker-compose works in the linux virtual environment under Windows
ifneq (,$(findstring Microsoft,$(VERSION)))
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
else
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
endif

export SERVICES_VERSION=1.0.2
export VCS_REF=$(shell git rev-parse --short HEAD) 
export BUILD_DATE=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

all:
	@echo 'run `make build-devel` to build your dev environment'
	@echo 'run `make up-devel` to start your dev environment.'
	@echo 'see Makefile for further targets'

build:	
	${DOCKER_COMPOSE} -f docker-compose.yml build

rebuild:
	${DOCKER_COMPOSE} -f docker-compose.yml build --no-cache

build-devel: .env
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build

rebuild-devel:
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build --no-cache

up:
	${DOCKER_COMPOSE} -f docker-compose.yml up

up-devel:
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml up

down:
	${DOCKER_COMPOSE} -f docker-compose.yml down

down-devel:
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml down

push_service_images:
	${DOCKER} login masu.speag.com
	${DOCKER} push masu.speag.com/simcore/services/dynamic/3d-viewer:${SERVICES_VERSION}

.env: .env-devel
	$(info #####  $< is newer than $@ ####)
	@diff -uN $@ $<
	@false

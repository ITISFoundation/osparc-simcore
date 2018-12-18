VERSION := $(shell uname -a)
# SAN this is a hack so that docker-compose works in the linux virtual environment under Windows
ifneq (,$(findstring Microsoft,$(VERSION)))
$(info    detected WSL)
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
else ifeq ($(OS), Windows_NT)
$(info    detected Powershell/CMD)
export DOCKER_COMPOSE=docker-compose.exe
export DOCKER=docker.exe
else
$(info    detected native linux)
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
endif


# export SERVICES_VERSION=1.0.5
export VCS_REF=$(shell git rev-parse --short HEAD) 
export BUILD_DATE=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
export SERVICE_PATH=simcore/services/dynamic/3d-viewer
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

build: check-env
	${DOCKER_COMPOSE} -f docker-compose.yml build

rebuild: check-env
	${DOCKER_COMPOSE} -f docker-compose.yml build --no-cache

build-devel: .env check-env
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build

rebuild-devel: .env check-env
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml build --no-cache

up:
	${DOCKER_COMPOSE} -f docker-compose.yml up

up-devel:
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml up

down:
	${DOCKER_COMPOSE} -f docker-compose.yml down
	${DOCKER_COMPOSE} -f docker-compose.yml -f docker-compose.devel.yml down

push_service_images: check-env
	${DOCKER} login ${DOCKER_REGISTRY}
	${DOCKER} push ${DOCKER_REGISTRY}/${SERVICE_PATH}:${SERVICES_VERSION}

.env: .env-devel
	$(info #####  $< is newer than $@ ####)
	@diff -uN $@ $<
	@false

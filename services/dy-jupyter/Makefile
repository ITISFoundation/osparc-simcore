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
	@echo 'run `make build` to build'
	@echo 'run `make up` to start'
	@echo 'see Makefile for further targets'

build:	
	${DOCKER_COMPOSE} -f docker-compose.yml build --build-arg VCS_REF=`git rev-parse --short HEAD` --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"`

rebuild:
	${DOCKER_COMPOSE} -f docker-compose.yml build --no-cache --build-arg VCS_REF=`git rev-parse --short HEAD` --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"`

up:
	${DOCKER_COMPOSE} -f docker-compose.yml up

down:
	${DOCKER_COMPOSE} -f docker-compose.yml down

SERVICES_VERSION=1.3
JUPYTER_SERVICE_NAME=masu.speag.com/simcore/services/jupyter-base-notebook
push_service_images:
	${DOCKER} login masu.speag.com
	${DOCKER} tag dy-jupyter_jupyter-base-notebook:latest ${JUPYTER_SERVICE_NAME}:${SERVICES_VERSION}
	${DOCKER} push ${JUPYTER_SERVICE_NAME}:${SERVICES_VERSION}
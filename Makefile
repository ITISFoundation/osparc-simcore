# author: Sylvain Anderegg

# TODO: add flavours by combinging docker-compose files. Namely development, test and production.
VERSION := $(shell uname -a)
# SAN this is a hack so that docker-compose works in the linux virtual environment under Windows
ifneq (,$(findstring Microsoft,$(VERSION)))
$(info    detected WSL)
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
export RUN_DOCKER_ENGINE_ROOT=1
# Windows does not have these things defined... but they are needed to execute a local swarm
export DOCKER_GID=1042
export HOST_GID=1000
else ifeq ($(OS), Windows_NT)
$(info    detected Powershell/CMD)
export DOCKER_COMPOSE=docker-compose.exe
export DOCKER=docker.exe
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

PY_FILES = $(strip $(shell find services packages -iname '*.py' -not -path "*egg*" -not -path "*contrib*" -not -path "*-sdk/python*" -not -path "*generated_code*" -not -path "*datcore.py"))

export PYTHONPATH=${CURDIR}/packages/s3wrapper/src:${CURDIR}/packages/simcore-sdk/src

all:
	@echo 'run `make build-devel` to build your dev environment'
	@echo 'run `make up-devel` to start your dev environment.'
	@echo 'see Makefile for further targets'

clean:
	@git clean -dxf -e .vscode/

build-devel:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml build

rebuild-devel:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml build --no-cache

up-devel:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.devel.yml -f services/docker-compose.tools.yml up

build:
	${DOCKER_COMPOSE} -f services/docker-compose.yml build

rebuild:
	${DOCKER_COMPOSE} -f services/docker-compose.yml build --no-cache

up:
	${DOCKER_COMPOSE} -f services/docker-compose.yml -f services/docker-compose.tools.yml up

up-swarm:
	${DOCKER} swarm init
	${DOCKER} stack deploy -c services/docker-compose.yml -c services/docker-compose.deploy.yml  -c services/docker-compose.tools.yml services

up-swarm-devel:
	${DOCKER} swarm init
	${DOCKER} stack deploy -c services/docker-compose.yml -c services/docker-compose.devel.yml -c services/docker-compose.deploy.devel.yml  -c services/docker-compose.tools.yml services

down:
	${DOCKER_COMPOSE} -f services/docker-compose.yml  -f services/docker-compose.tools.yml down
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

pylint:
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes
	/bin/bash -c "pylint --rcfile=.pylintrc $(PY_FILES)"

before_test:
	${DOCKER_COMPOSE} -f packages/pytest_docker/tests/docker-compose.yml pull
	${DOCKER_COMPOSE} -f packages/pytest_docker/tests/docker-compose.yml build
	${DOCKER_COMPOSE} -f packages/s3wrapper/tests/docker-compose.yml pull
	${DOCKER_COMPOSE} -f packages/s3wrapper/tests/docker-compose.yml build
	${DOCKER_COMPOSE} -f packages/simcore-sdk/tests/docker-compose.yml pull
	${DOCKER_COMPOSE} -f packages/simcore-sdk/tests/docker-compose.yml build

run_test:
	pytest -v apis/tests
	pytest -v services/apihub/tests
	pytest --cov=pytest_docker -v packages/pytest_docker/tests
	pytest --cov=s3wrapper -v packages/s3wrapper/tests
	pytest --cov=simcore_sdk -v packages/simcore-sdk/tests
	pytest --cov=simcore_service_webserver -v services/web/server/tests
	pytest --cov=simcore_service_director -v services/director/tests
	pytest --cov=simcore_service_storage -v -m "not travis" services/storage/tests

after_test:
	# leave a clean slate (not sure whether this is actually needed)
	${DOCKER_COMPOSE} -f packages/pytest_docker/tests/docker-compose.yml down
	${DOCKER_COMPOSE} -f packages/s3wrapper/tests/docker-compose.yml down
	${DOCKER_COMPOSE} -f packages/simcore-sdk/tests/docker-compose.yml down

test:
	make before_test
	make run_test
	make after_test

PLATFORM_VERSION=3.16

push_platform_images:
	${DOCKER} login masu.speag.com
	${DOCKER} tag services_apihub:latest masu.speag.com/simcore/workbench/apihub:${PLATFORM_VERSION}
	${DOCKER} push masu.speag.com/simcore/workbench/apihub:${PLATFORM_VERSION}
	${DOCKER} tag services_webserver:latest masu.speag.com/simcore/workbench/webserver:${PLATFORM_VERSION}
	${DOCKER} push masu.speag.com/simcore/workbench/webserver:${PLATFORM_VERSION}
	${DOCKER} tag services_sidecar:latest masu.speag.com/simcore/workbench/sidecar:${PLATFORM_VERSION}
	${DOCKER} push masu.speag.com/simcore/workbench/sidecar:${PLATFORM_VERSION}
	${DOCKER} tag services_director:latest masu.speag.com/simcore/workbench/director:${PLATFORM_VERSION}
	${DOCKER} push masu.speag.com/simcore/workbench/director:${PLATFORM_VERSION}

  setup-check: .env .vscode/settings.json

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



.PHONY: all clean build-devel rebuild-devel up-devel build up down test after_test push_platform_images

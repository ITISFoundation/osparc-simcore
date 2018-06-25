# author: Sylvain Anderegg

# TODO: add flavours by combinging docker-compose files. Namely development, test and production.

PY_FILES = $(strip $(shell find services packages -iname '*.py'))

export PYTHONPATH=${CURDIR}/packages/s3wrapper/src:${CURDIR}/packages/simcore-sdk/src

build-devel:
	docker-compose -f services/docker-compose.yml -f services/docker-compose.devel.yml build

rebuild-devel:
	docker-compose -f services/docker-compose.yml -f services/docker-compose.devel.yml build --no-cache

up-devel:
	docker-compose -f services/docker-compose.yml -f services/docker-compose.devel.yml up

build:
	docker-compose -f services/docker-compose.yml build

rebuild:
	docker-compose -f services/docker-compose.yml build --no-cache

up:
	docker-compose -f services/docker-compose.yml up

up-swarm:
	docker swarm init
	docker stack deploy -c services/docker-compose.yml -c services/docker-compose.deploy.yml services

down:
	docker-compose -f services/docker-compose.yml down
	docker-compose -f services/docker-compose.yml -f services/docker-compose.devel.yml down

down-swarm:
	docker stack rm services
	docker swarm leave -f

stack-up:
	docker swarm init

stack-down:
	docker stack rm osparc
	docker swarm leave -f

pylint:
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes
	/bin/bash -c "pylint --rcfile=.pylintrc $(PY_FILES)"

before_test:
	docker-compose -f packages/pytest_docker/tests/docker-compose.yml pull
	docker-compose -f packages/pytest_docker/tests/docker-compose.yml build
	docker-compose -f packages/s3wrapper/tests/docker-compose.yml pull
	docker-compose -f packages/s3wrapper/tests/docker-compose.yml build
	docker-compose -f packages/simcore-sdk/tests/docker-compose.yml pull
	docker-compose -f packages/simcore-sdk/tests/docker-compose.yml build

run_test:
	pytest --cov=pytest_docker -v packages/pytest_docker/
	pytest --cov=s3wrapper -v packages/s3wrapper/
	pytest -v packages/simcore-sdk/

after_test:
	# leave a clean slate (not sure whether this is actually needed)
	docker-compose -f packages/pytest_docker/tests/docker-compose.yml down
	docker-compose -f packages/s3wrapper/tests/docker-compose.yml down
	docker-compose -f packages/simcore-sdk/tests/docker-compose.yml down

test:
	make before_test
	make run_test
	make after_test

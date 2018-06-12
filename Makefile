# author: Sylvain Anderegg

# TODO: add flavours by combinging docker-compose files. Namely development, test and production.

PY_FILES = $(strip $(shell find services modules -iname '*.py'))


build:
	docker-compose -f services/docker-compose.yml build

rebuild:
	docker-compose -f services/docker-compose.yml build --no-cache

up:
	docker swarm init
	docker-compose -f services/docker-compose.yml -f services/docker-compose.deploy.yml up

down:
	docker-compose -f services/docker-compose.yml -f services/docker-compose.deploy.yml down
	docker swarm leave -f

pylint:
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes
	/bin/bash -c "pylint --rcfile=.pylintrc $(PY_FILES)"

test:
	export PYTHONPATH=${PWD}/packages/s3wrapper/src
	docker-compose -f packages/pytest_docker/tests/docker-compose.yml pull
	docker-compose -f packages/pytest_docker/tests/docker-compose.yml build
	docker-compose -f packages/s3wrapper/tests/docker-compose.yml pull
	docker-compose -f packages/s3wrapper/tests/docker-compose.yml build
	docker-compose -f packages/simcore-sdk/tests/docker-compose.yml pull
	docker-compose -f packages/simcore-sdk/tests/docker-compose.yml build
	pytest -v packages/pytest_docker/
	pytest -v packages/s3wrapper/
	pytest -v packages/simcore-sdk/

# author: Sylvain Anderegg

# TODO: add flavours by combinging docker-compose files. Namely development, test and production.

PY_FILES = $(strip $(shell find services packages -iname '*.py'))

export PYTHONPATH=${PWD}/packages/s3wrapper/src

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

before_test:
	docker-compose -f packages/pytest_docker/tests/docker-compose.yml pull
	docker-compose -f packages/pytest_docker/tests/docker-compose.yml build
	docker-compose -f packages/s3wrapper/tests/docker-compose.yml pull
	docker-compose -f packages/s3wrapper/tests/docker-compose.yml build
	docker-compose -f packages/simcore-sdk/tests/docker-compose.yml pull
	docker-compose -f packages/simcore-sdk/tests/docker-compose.yml build

run_test:
	pytest -v packages/pytest_docker/
	pytest -v packages/s3wrapper/
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

# author: Sylvain Anderegg

# TODO: add flavours by combinging docker-compose files. Namely development, test and production.

PY_FILES = $(strip $(shell find services -iname '*.py'))


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
	/bin/bash -c "pylint --rcfile=.pylintrc --disable=import-error --disable=fixme --disable=C $(PY_FILES)"

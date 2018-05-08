# Pipelines Project Make File
# author: Sylvain Anderegg

PY_FILES = $(strip $(shell find services -iname '*.py'))

build:
	docker-compose -f services/docker-compose.yml build --no-cache

demo:
	docker swarm init
	docker-compose -f services/docker-compose.yml up

start:
	docker swarm init
	docker-compose -f services/docker-compose.yml up

stop:
	docker-compose -f services/docker-compose.yml down
	docker swarm leave -f

pylint:
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes
	/bin/bash -c "pylint --rcfile=.pylintrc --disable=import-error --disable=fixme $(PY_FILES)"

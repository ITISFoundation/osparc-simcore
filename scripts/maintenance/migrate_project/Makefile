.DEFAULT_GOAL := build

SHELL := /bin/bash

IMAGE_NAME := migrate-utils
TAG := latest
CFG_NAME := cfg.ignore.json

build:
	# creating python virtual environment
	docker-compose -f docker-compose-build.yaml build

shell:
	docker run -it --rm ${IMAGE_NAME}:${TAG} bash

empty-config-file:	# empty configuration file to fill up
	docker run -it --rm \
	${IMAGE_NAME}:${TAG} python models.py > ${CFG_NAME}

migrate:
	docker run -it --rm \
	-v ${PWD}/${CFG_NAME}:/tmp/cfg.json \
	${IMAGE_NAME}:${TAG} python cli.py --config /tmp/cfg.json

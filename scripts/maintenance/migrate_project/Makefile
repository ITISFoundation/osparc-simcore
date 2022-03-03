.DEFAULT_GOAL := build

SHELL := /bin/bash

IMAGE_NAME := migrate-utils
TAG := latest

build:
	# creating python virtual environment
	docker-compose -f docker-compose-build.yaml build

shell:
	docker run -it --rm ${IMAGE_NAME}:${TAG} bash

empty-config-file:	# empty configuration file to fill up
	docker run -it --rm \
	${IMAGE_NAME}:${TAG} python models.py > cfg.json

migrate:
	docker run -it --rm \
	-v ${PWD}/cfg.json:/tmp/cfg.json \
	${IMAGE_NAME}:${TAG} python cli.py /tmp/cfg.json

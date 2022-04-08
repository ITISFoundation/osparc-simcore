.DEFAULT_GOAL := build

SHELL := /bin/bash

CFG_NAME	:= cfg.ignore.json
REPO_DIR	:= $(CURDIR)/../../..
IMAGE_NAME	:= migrate-utils
TAG			:= latest

build:
	docker build -t ${IMAGE_NAME} --file $(PWD)/Dockerfile $(REPO_DIR)

shell:
	docker run -it --rm ${IMAGE_NAME}:${TAG} bash

empty-config-file:	# empty configuration file to fill up
	docker run -it --rm \
	${IMAGE_NAME}:${TAG} python models.py > ${CFG_NAME}

migrate:
	docker run -it --rm \
	-v ${PWD}/${CFG_NAME}:/tmp/cfg.json \
	${IMAGE_NAME}:${TAG} python cli.py --config /tmp/cfg.json

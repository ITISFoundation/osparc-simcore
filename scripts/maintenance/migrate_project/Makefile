.DEFAULT_GOAL := help

SHELL := /bin/bash

REPO_DIR	:= $(CURDIR)/../../..
IMAGE_NAME	:= migrate-utils
TAG			:= latest

.PHONY: help

help: ## help on rule's targets
ifeq ($(IS_WIN),)
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
else
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
endif

.PHONY: build
build: ## Builds docker container for the migration. Run this first.
	docker build -t ${IMAGE_NAME} --file $(PWD)/Dockerfile $(REPO_DIR)

.PHONY: shell
debug-shell: ## Runs a bash inside the container that performs the migrate. For manual interventions and debuging.
	docker run -it --rm ${IMAGE_NAME}:${TAG} bash

.PHONY: cfg.template.json
cfg.template.json:	## creates an empty configuration file to fill up
	docker run -it --rm \
	${IMAGE_NAME}:${TAG} python models.py > $@

.PHONE: migrate
migrate: cfg.json ## Performs migrate (a.k.a. copying) of a study from one deployment to another. Run `make build` first. Supported S3 providers are `CEPH`, `AWS`, `MINIO`.
	docker run -it --rm \
	-v ${PWD}/${CFG_NAME}:/tmp/cfg.json \
	${IMAGE_NAME}:${TAG} python cli.py --config /tmp/cfg.json

.DEFAULT_GOAL := help

SHELL := /bin/bash

CFG_NAME 	:= "cfg.json"
REPO_DIR	:= $(CURDIR)/../../..
IMAGE_NAME	:= migrate-utils
TAG			:= latest

.PHONY: help

help: ## help on rule's targets
	# ⚠️ IMPORTANT PITFALLS
	# 💣 No postgres database version migration is performed at the moment. This migration **only works for **identical databases**: source and target.
	# 🚨 If a file's or project's UUID already exist in the destination database (collision), this script will fail with an error.
	# ✅ Supported S3 providers are `CEPH`, `AWS`, `MINIO`, `RUSTFS`
	@awk 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: build
build: ## Builds docker container for the migration. Run this first.
	docker buildx build --load --tag ${IMAGE_NAME} --file $(PWD)/Dockerfile $(REPO_DIR)

.PHONY: debug-shell
debug-shell: ## Runs a bash inside the container that performs the migrate. For manual interventions and debugging.
	docker run --interactive --tty --rm ${IMAGE_NAME}:${TAG} bash

.PHONY: cfg.json
cfg.json:	## creates an empty configuration file to fill up
	docker run --interactive --tty --rm \
	${IMAGE_NAME}:${TAG} python models.py > ${CFG_NAME}

.PHONE: migrate
migrate: ## Performs migrate (a.k.a. copying) of a study from one deployment to another. Run `make build` first. Supported S3 providers are `CEPH`, `AWS`, `MINIO`, `RUSTFS`.
	docker run -it --rm \
	-v ${PWD}/${CFG_NAME}:/tmp/cfg.json \
	${IMAGE_NAME}:${TAG} python cli.py --config /tmp/cfg.json

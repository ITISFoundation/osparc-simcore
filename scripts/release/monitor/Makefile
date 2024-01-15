.DEFAULT_GOAL := help

SHELL := /bin/bash


help: ## help on rule's targets
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)


.PHONY: install install-dev
install install-dev: ## installation and check
	# installation
	@pip install $(if $(findstring -dev, $@),-e,) .
	# check executable runs
	monitor-release --help

.DEFAULT_GOAL := help

SHELL := /bin/bash

PYTHON_VERSION := $(or $(PYTHON), 3.13)


.PHONY: hel%
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
hel%:
	@echo "usage: make [target] ..."
	@echo ""
	@echo "Targets for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

.venv:
	# creating python virtual environment
	@uv venv --python=$(PYTHON_VERSION)

install: .venv ## installs using $PYTHON_VERSION or uses defaults
	# installing package
	@uv pip install --python=$(PYTHON_VERSION) .
	# now you can call the maintenance scripts
	# source .venv/bin/activate
	# autoscaled-monitor --deploy-config PATH/TO/REPO.CONFIG summary

install-dev: .venv ## installs in devel mode using PYTHON_VERSION or uses defaults
	# installing package
	@uv pip install -e .
	# now you can call the maintenance scripts
	# source .venv/bin/activate
	# autoscaled-monitor --deploy-config PATH/TO/REPO.CONFIG summary

.DEFAULT_GOAL := help

SHELL := /bin/bash

PYTHON_VERSION := $(or $(PYTHON), 3.13)

# dask-sidecar pins the dask version that the computational cluster runs.
# This client MUST talk to the cluster with the very same dask version.
DASK_SIDECAR_REQUIREMENTS := ../../../services/dask-sidecar/requirements/_dask-distributed.txt

REPO_BASE_DIR := $(shell git rev-parse --show-toplevel)
include $(REPO_BASE_DIR)/scripts/makefiles/help.mk

.venv:
	# creating python virtual environment
	@uv venv --python=$(PYTHON_VERSION)

install: .venv ## installs using $PYTHON_VERSION or uses defaults
	# installing locked dependencies (see uv.lock)
	@uv sync --python=$(PYTHON_VERSION) --no-editable
	# now you can call the maintenance scripts
	# source .venv/bin/activate
	# autoscaled-monitor --deploy-config PATH/TO/REPO.CONFIG summary

install-dev: .venv ## installs in devel mode using PYTHON_VERSION or uses defaults
	# installing locked dependencies in editable mode (see uv.lock)
	@uv sync --python=$(PYTHON_VERSION)
	# now you can call the maintenance scripts
	# source .venv/bin/activate
	# autoscaled-monitor --deploy-config PATH/TO/REPO.CONFIG summary

sync-dask-version: ## upgrades uv.lock while pinning dask to the dask-sidecar version
	$(eval DASK_VERSION := $(shell grep -E '^dask==' $(DASK_SIDECAR_REQUIREMENTS) | sed -E 's/^dask==([^ #]+).*/\1/'))
	@if [ -z "$(DASK_VERSION)" ]; then echo "ERROR: could not read dask version from $(DASK_SIDECAR_REQUIREMENTS)"; exit 1; fi
	@echo "Pinning dask[distributed]==$(DASK_VERSION) (from dask-sidecar)"
	@uv add "dask[distributed]==$(DASK_VERSION)"

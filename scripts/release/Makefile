.DEFAULT_GOAL := help

SHELL := /bin/bash

REPO_BASE_DIR := $(shell git rev-parse --show-toplevel)
include $(REPO_BASE_DIR)/scripts/makefiles/help.mk


.PHONY: install install-dev
install install-dev: ## installation and check
	# installation
	@pip install $(if $(findstring -dev, $@),-e,) .
	# check executable runs
	monitor-release --help

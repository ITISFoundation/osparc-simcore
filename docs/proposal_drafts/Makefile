.DEFAULT_GOAL := help

SHELL := /bin/bash

DATE := $(shell date +%Y-%m-%d)

.PHONY: help

help: ## prints this message
ifeq ($(IS_WIN),)
	@awk 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
else
	@awk 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
endif


new-draft: ## create a new draft usage: make new-draft name=NEW_FEATURE_NAME
	$(eval FILE_NAME='${DATE}_${name}.md')
	@cp .draft_template.md '${FILE_NAME}'
	@echo "created ${FILE_NAME}"

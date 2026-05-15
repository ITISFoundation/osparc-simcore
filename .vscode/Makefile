.DEFAULT_GOAL := help

include ../scripts/common-templates.Makefile

VSCODE_CONFIGS := settings.json launch.json mcp.json

.PHONY: help all

help: ## displays available targets
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

all: $(VSCODE_CONFIGS) ## creates all vscode config files from templates

%.json: %.template.json ## creates json file from template counterpart
	$(clone_from_template)

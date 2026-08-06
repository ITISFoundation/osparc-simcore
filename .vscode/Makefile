.DEFAULT_GOAL := help

include ../scripts/common-templates.Makefile

VSCODE_CONFIGS := settings.json launch.json mcp.json

REPO_BASE_DIR := $(shell git rev-parse --show-toplevel)
include $(REPO_BASE_DIR)/scripts/makefiles/help.mk

all: $(VSCODE_CONFIGS) ## creates all vscode config files from templates

%.json: %.template.json ## creates json file from template counterpart
	$(clone_from_template)

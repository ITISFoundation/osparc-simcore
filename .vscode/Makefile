.DEFAULT_GOAL := help

include ../scripts/makefiles/templates.mk

VSCODE_CONFIGS := settings.json launch.json mcp.json

REPO_BASE_DIR := $(shell git rev-parse --show-toplevel)
include $(REPO_BASE_DIR)/scripts/makefiles/help.mk

all: $(VSCODE_CONFIGS) ## creates all vscode config files from templates

launch.json: launch.template.json ## creates launch.json from its template, with the dev slot's debug ports
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, rendering $< as $@ ############"; \
	python3 $(REPO_BASE_DIR)/scripts/dev_slot.py shift-ports --env-file $(REPO_BASE_DIR)/.env < $< > $@)

%.json: %.template.json ## creates json file from template counterpart
	$(clone_from_template)

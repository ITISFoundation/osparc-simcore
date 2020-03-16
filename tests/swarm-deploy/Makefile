#
# Targets for DEVELOPMENT for system tests
#
include ../../scripts/common.Makefile

ROOT_DIR  = $(abspath $(CURDIR)/../../)
VENV_DIR ?= $(abspath $(ROOT_DIR)/.venv)


requirements.txt: requirements.in
	# pip compiling $<
	@$(VENV_DIR)/bin/pip-compile --output-file $@ $<


.PHONY: install
install: $(VENV_DIR) requirements.txt ## installs dependencies
	# installing requirements
	@$</bin/pip3 install -r requirements.txt


.PHONY: tests
tests: ## runs all tests [DEV]
	# running unit tests
	@$(VENV_DIR)/bin/pytest -vv -x --ff --pdb $(CURDIR)

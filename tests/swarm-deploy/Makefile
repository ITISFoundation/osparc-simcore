#
# Targets for DEVELOPMENT for system tests
#
include ../../scripts/common.Makefile

ROOT_DIR  = $(abspath $(CURDIR)/../../)
VENV_DIR ?= $(abspath $(ROOT_DIR)/.venv)

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install
install: $(VENV_DIR) requirements ## installs dependencies
	# installing requirements
	@$</bin/pip3 install -r requirements/ci.txt


.PHONY: tests
tests: ## runs all tests [DEV]
	# running unit tests
	@$(VENV_DIR)/bin/pytest -vv -x --ff --pdb $(CURDIR)

#
# Targets for DEVELOPMENT for system tests
#
include ../../scripts/common.Makefile


.PHONY: requirements
requirements reqs: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install
install:  ## installs dependencies
	# installing requirements
	@$(VENV_DIR)/bin/pip3 install -r requirements/ci.txt


.PHONY: tests
tests: ## runs all tests
	# running unit tests
	@$(VENV_DIR)/bin/pytest -vv -x --ff --pdb $(CURDIR)

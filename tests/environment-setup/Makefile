#
# Targets for DEVELOPMENT for system tests
#
include ../../scripts/common.Makefile


.PHONY: requirements
requirements reqs: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install install-dev install-prod install-ci

install:  install-ci

install-dev install-prod install-ci:  ## install requirements in dev/prod/ci mode
	# installing in $(subst install-,,$@) mode
	@$(VENV_DIR)/bin/pip3 install -r requirements/$(subst install-,,$@).txt


.PHONY: tests
tests: ## runs all tests
	# running unit tests
	@$(VENV_DIR)/bin/pytest -vv -x --ff --pdb $(CURDIR)

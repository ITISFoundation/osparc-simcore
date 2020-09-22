#
# Targets for DEVELOPMENT for system tests
#
include ../../scripts/common.Makefile


.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install
install: _check_venv_active  ## installs dependencies
	# installing requirements
	python -m pip install -r requirements/ci.txt


.PHONY: tests
tests: _check_venv_active ## runs all tests [DEV]
	# running unit tests
	pytest -vv -x --ff --pdb $(CURDIR)

#
# Targets for DEVELOPMENT of openapi-api specifications (OAS) for osparc-simcore services
#
include ../scripts/common.Makefile



.PHONY: install-dev install-ci

install-dev install-ci: _check_venv_active ## install app in development/CI mode
	# Installing in $(subst install-,,$@) mode
	pip-sync --pip-args="--use-feature=in-tree-build" requirements/$(subst install-,,$@).txt


.PHONY: test
test: _check_venv_active ## runs all tests [DEV]
	# running unit tests
	pytest -vv --exitfirst --failed-first  --durations=10 --pdb $(CURDIR)/tests

#
# Targets for DEVELOPMENT of Service Library
#
include ../../scripts/common.Makefile


.PHONY: install-dev install-dev[aiohttp] install-ci
install-dev install-dev[aiohttp] install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


.PHONY: tests test-minimal test-aiohttp
test-dev: ## runs unit tests w/o extras (assumes 'make install-dev')
	# running unit tests [minimal]
	@pytest -vv --exitfirst --ignore=tests/aiohttp --failed-first --durations=10 --pdb $(CURDIR)/tests

test-aiohttp: ## runs unit aiohttp tests (assumes 'make install-dev_aiohttp')
	# running unit tests [aiohttp]
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests/aiohttp

tests: ## runs ALL tests (assumes 'make install-dev_aiohttp')
	# running unit tests [ALL]
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests

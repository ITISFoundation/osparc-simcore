#
# Targets for DEVELOPMENT of Service Library
#
include ../../scripts/common.Makefile


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt


.PHONY: tests-ci
tests-ci: ## runs unit tests inside CI
	# running unit tests inside CI
	@pytest -vv --asyncio-mode=auto --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests

#
# Targets for DEVELOPMENT of Service Library
#
include ../../scripts/common.Makefile

REPO_BASE_DIR  = $(abspath $(CURDIR)/../../)


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@pip3 install -r requirements/$(subst install-,,$@).txt


.PHONY: tests
tests: ## runs unit tests
	# running unit tests
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests

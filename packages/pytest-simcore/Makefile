#
# Targets for DEVELOPMENT of Service Library
#
include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/package.mk

PYTEST_BASE_ARGS := --asyncio-mode=auto --durations=10
PYTEST_ARGS_ci := --exitfirst --failed-first --pdb -vv


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt


.PHONY: tests-ci

# CI-CONTRACT: tests-ci is invoked by ci/github/**/*.bash
tests-ci: test-ci-unit ## runs unit tests inside CI [CI]

#
# Targets for DEVELOPMENT of models Library
#
include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/package.mk

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt


PYTEST_ASYNCIO_ARGS :=

.PHONY: tests tests-ci
tests: test-dev-unit ## runs unit tests

# CI-CONTRACT: tests-ci is invoked by ci/github/**/*.bash
tests-ci: test-ci-unit ## runs unit tests in CI mode [CI]

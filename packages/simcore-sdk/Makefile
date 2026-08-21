# osparc-simcore general makefile
#
# NOTES:
# 	- GNU make version 4.2 recommended
# 	- Use 'make -n *' to dry-run during debugging
# 	- In windows, only WSL is supported
#
# by sanderegg, pcrespov
#
include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/package.mk


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt

TEST_TARGET := $(CURDIR)/tests/unit
PYTEST_BASE_ARGS += --keep-docker-up

.PHONY: test-ci-integration test-dev-integration tests-unit tests-unit-ci tests-integration tests-integration-ci tests

test-dev-integration: TEST_TARGET := $(CURDIR)/tests/integration
test-dev-integration: PYTEST_BASE_ARGS += --cov-report=xml $(PYTEST_JUNIT_ARGS)
test-dev-integration: PYTEST_ARGS_dev := --exitfirst --failed-first --pdb --verbose
test-dev-integration: ## runs integration tests against local+production images
	@export DOCKER_REGISTRY=local; \
	export DOCKER_IMAGE_TAG=production; \
	$(MAKE) --no-print-directory _run-test-dev \
		TEST_TARGET="$(TEST_TARGET)" \
		PYTEST_BASE_ARGS='$(PYTEST_BASE_ARGS)' \
		PYTEST_ARGS_dev='$(PYTEST_ARGS_dev)'

test-ci-integration: TEST_TARGET := $(CURDIR)/tests/integration
test-ci-integration: PYTEST_ARGS_ci += --disk-usage --disk-usage-threshold=20 --log-cli-level=WARNING
test-ci-integration: ## runs integration tests with CI parameters
	@$(MAKE) --no-print-directory _run-test-ci \
		TEST_TARGET="$(TEST_TARGET)" \
		PYTEST_BASE_ARGS='$(PYTEST_BASE_ARGS)' \
		PYTEST_ARGS_ci='$(PYTEST_ARGS_ci)'

tests-unit: test-dev-unit ## runs unit tests

# CI-CONTRACT: tests-unit-ci is invoked by ci/github/**/*.bash
tests-unit-ci: test-ci-unit ## runs unit tests with CI parameters [CI]

tests-integration: test-dev-integration ## runs integration tests against local+production images

# CI-CONTRACT: tests-integration-ci is invoked by ci/github/**/*.bash
tests-integration-ci: test-ci-integration ## runs integration tests with CI parameters [CI]

tests: tests-unit tests-integration ## runs all tests

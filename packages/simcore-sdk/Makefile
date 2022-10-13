# osparc-simcore general makefile
#
# NOTES:
# 	- GNU make version 4.2 recommended
# 	- Use 'make -n *' to dry-run during debugging
# 	- In windows, only WSL is supported
#
# by sanderegg, pcrespov
#
include ../../scripts/common.Makefile
include ../../scripts/common-package.Makefile


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt

.PHONY: test-dev-unit test-ci-unit test-dev-integration test-ci-integration tests
test-dev-unit: ## runs unit tests
	# running unit tests
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov=simcore_sdk \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--keep-docker-up \
		--pdb \
		-vv \
		$(CURDIR)/tests/unit

test-ci-unit: ## runs unit tests with ci parameters
	# running unit tests
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-append \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=simcore_sdk \
		--durations=10 \
		--keep-docker-up \
		--log-date-format="%Y-%m-%d %H:%M:%S" \
    --log-format="%(asctime)s %(levelname)s %(message)s" \
		--verbose \
		-m "not heavy_load" \
		$(CURDIR)/tests/unit

test-dev-integration: ## runs integration tests against local+production images
	# running integration tests local/(service):production images ...
	@export DOCKER_REGISTRY=local; \
	export DOCKER_IMAGE_TAG=production; \
	pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=simcore_sdk \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--keep-docker-up \
		--pdb \
		--verbose \
		$(CURDIR)/tests/integration

test-ci-integration: ## runs integration tests against local+production images with CI parameters
	pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-append \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=simcore_sdk \
		--durations=10 \
		--keep-docker-up \
		--log-date-format="%Y-%m-%d %H:%M:%S" \
		--verbose \
		-m "not heavy_load" \
		--log-format="%(asctime)s %(levelname)s %(message)s" \
		$(CURDIR)/tests/integration

tests: test-dev-unit test-dev-integration ## runs all tests
	# running tests

#
# Targets for DEVELOPMENT of Service Library
#
include ../../scripts/makefiles/common.mk

help:	## overwrites and calls common help function
	$(MAKE) --no-print-directory --file ../../scripts/makefiles/common.mk $@
	@echo
	@echo '🚨 BEWARE there are issues with brackets in names `make test-dev[aiohttp]` will raise errors:'
	@echo '✅` `make "test-dev[aiohttp]"` works as intended'
	@echo '👓 Please note: when INSTALLING, DEVELOPING and TESTING '
	@echo
	@echo 'servicelib support for aiohttp extras is not included:'
	@echo '- `make install-dev`: common features w/o any extras'
	@echo '- `make "install-dev[aiohttp]"`: w/ aiohttp extras'
	@echo '- `make "install-dev[fastapi]"`: w/ fastapi extras'
	@echo '- `make "install-dev[all]"`: w/ all extras'


.PHONY: "install-dev" "install-dev[aiohttp]" "install-dev[fastapi]" "install-dev[all]"
.PHONY: "install-ci" "install-ci[aiohttp]" "install-ci[fastapi]" "install-ci[all]"

install-%: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt

PYTEST_COV_TARGET := servicelib
TEST_TARGET := $(CURDIR)/tests

PYTEST_BASE_ARGS = \
	--asyncio-mode=auto \
	--color=yes \
	--cov-config=$(CURDIR)/../../.coveragerc \
	--cov-report=term-missing \
	--cov-report=xml \
	--cov=$(PYTEST_COV_TARGET) \
	--durations=10 \
	--junitxml=junit.xml -o junit_family=legacy \
	--keep-docker-up

PYTEST_ARGS_dev = \
	--exitfirst \
	--failed-first \
	--pdb \
	-vv

PYTEST_ARGS_ci = \
	--cov-append \
	--log-date-format="%Y-%m-%d %H:%M:%S" \
	--log-format="%(asctime)s %(levelname)s %(message)s" \
	--verbose \
	-m "not heavy_load"

include ../../scripts/makefiles/python-test.mk

.PHONY: test test-dev test-dev-unit test-ci-unit test-dev[aiohttp] test-dev[fastapi] test-dev[all] test-ci[all]

test: test-dev ## runs unit tests without extras

test-dev: PYTEST_ADDITIONAL_PARAMETERS := --ignore=tests/aiohttp --ignore=tests/fastapi
test-dev: ## runs unit tests without extras
	@$(MAKE) --no-print-directory _run-test-dev \
		PYTEST_ADDITIONAL_PARAMETERS='$(PYTEST_ADDITIONAL_PARAMETERS)'

test-dev-unit: test-dev ## runs unit tests without extras

test-ci-unit: test-ci[all] ## runs unit tests with all extras in CI mode

test-dev[aiohttp]: PYTEST_ADDITIONAL_PARAMETERS := --ignore=tests/fastapi
test-dev[aiohttp]: ## runs unit common tests and aiohttp extras
	@$(MAKE) --no-print-directory _run-test-dev \
		PYTEST_ADDITIONAL_PARAMETERS='$(PYTEST_ADDITIONAL_PARAMETERS)'

test-dev[fastapi]: PYTEST_ADDITIONAL_PARAMETERS := --ignore=tests/aiohttp
test-dev[fastapi]: ## runs unit common tests and fastapi extras
	@$(MAKE) --no-print-directory _run-test-dev \
		PYTEST_ADDITIONAL_PARAMETERS='$(PYTEST_ADDITIONAL_PARAMETERS)'

test-dev[all]: ## runs unit tests with all extras
	@$(MAKE) --no-print-directory _run-test-dev

# CI-CONTRACT: test-ci[all] is invoked by ci/github/**/*.bash
test-ci[all]: ## runs unit tests with all extras in CI mode [CI]
	@$(MAKE) --no-print-directory _run-test-ci

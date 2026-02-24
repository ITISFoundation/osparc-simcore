#
# Targets for DEVELOPMENT of Service Library
#
# This library supports optional extras for different frameworks:
# - aiohttp: for aiohttp framework support
# - fastapi: for fastapi framework support (if defined in pyproject.toml)
#
# USAGE:
#   make install-dev                  # install without extras
#   make "install-dev[aiohttp]"       # install with aiohttp extra
#   make "install-dev[fastapi]"       # install with fastapi extra
#   make "install-dev[all]"           # install with all extras
#   make tests                        # run tests without extras
#   make "tests[aiohttp]"             # run tests for aiohttp only
#
# NOTE: Shell requires quotes around targets with brackets.
#

include ../../scripts/common.Makefile
include ../../scripts/common-package.Makefile

# Package-specific configuration
COV_PACKAGE_NAME := servicelib
EXTRAS := aiohttp fastapi
PYTEST_OPTS := --keep-docker-up

# Override help to show extras info first, then common targets + package-specific extras
# This ensures $(MAKEFILE_LIST) includes all Makefiles (common.Makefile + common-package.Makefile + this file)
.PHONY: help
help:
	@echo
	@echo "ℹ️  Service Library Extras:"
	@echo "   Targets with brackets require shell quotes: make \"TARGETS[extra]\""
	@echo "   Examples:"
	@echo "   ❌ make install-dev[aiohttp]"
	@echo "   ✅ make \"install-dev[aiohttp]\""
	@echo
	@echo "Available extras: $(EXTRAS)"
	@echo
	@echo "---"
	@echo "usage: make [target] ..."
	@echo ""
	@echo "Targets for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_\[\]-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""


#
# INSTALL TARGETS WITH EXTRAS
#

.PHONY: install-dev[all]
install-dev[all]: _check_venv_active ## install dev dependencies with all extras
	@uv sync --active --all-groups --extra aiohttp --extra fastapi

.PHONY: "install-dev[aiohttp]"
install-dev[aiohttp]: _check_venv_active ## install dev dependencies with aiohttp extra
	@uv sync --active --all-groups --extra aiohttp

.PHONY: "install-dev[fastapi]"
install-dev[fastapi]: _check_venv_active ## install dev dependencies with fastapi extra
	@uv sync --active --all-groups --extra fastapi


.PHONY: install-ci[all]
install-ci[all]: _check_venv_active ## install CI dependencies with all extras
	@uv sync --active --group dev --extra aiohttp --extra fastapi

.PHONY: "install-ci[aiohttp]"
install-ci[aiohttp]: _check_venv_active ## install CI dependencies with aiohttp extra
	@uv sync --active --group dev --extra aiohttp

.PHONY: "install-ci[fastapi]"
install-ci[fastapi]: _check_venv_active ## install CI dependencies with fastapi extra
	@uv sync --active --group dev --extra fastapi


.PHONY: install-prod[all]
install-prod[all]: _check_venv_active ## install prod dependencies with all extras
	@uv sync --active --no-dev --extra aiohttp --extra fastapi

.PHONY: "install-prod[aiohttp]"
install-prod[aiohttp]: _check_venv_active ## install prod dependencies with aiohttp extra
	@uv sync --active --no-dev --extra aiohttp

.PHONY: "install-prod[fastapi]"
install-prod[fastapi]: _check_venv_active ## install prod dependencies with fastapi extra
	@uv sync --active --no-dev --extra fastapi


#
# TEST TARGETS WITH EXTRAS
#

.PHONY: tests[all]
tests[all]: _check_venv_active ## run tests with all extras
	@pytest $(PYTEST_OPTS) \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=$(COV_PACKAGE_NAME) \
		--durations=10 \
		--junitxml=junit.xml -o junit_family=legacy \
		--exitfirst \
		--failed-first \
		--pdb \
		-vv \
		$(CURDIR)/tests

.PHONY: "tests[aiohttp]"
tests[aiohttp]: _check_venv_active ## run tests for aiohttp only
	@pytest $(PYTEST_OPTS) \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=$(COV_PACKAGE_NAME) \
		--durations=10 \
		--junitxml=junit.xml -o junit_family=legacy \
		--exitfirst \
		--failed-first \
		--ignore=$(CURDIR)/tests/fastapi \
		--pdb \
		-vv \
		$(CURDIR)/tests

.PHONY: "tests[fastapi]"
tests[fastapi]: _check_venv_active ## run tests for fastapi only
	@pytest $(PYTEST_OPTS) \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=$(COV_PACKAGE_NAME) \
		--durations=10 \
		--junitxml=junit.xml -o junit_family=legacy \
		--exitfirst \
		--failed-first \
		--ignore=$(CURDIR)/tests/aiohttp \
		--pdb \
		-vv \
		$(CURDIR)/tests


.PHONY: tests-ci[all]
tests-ci[all]: _check_venv_active ## run CI tests with all extras
	@pytest $(PYTEST_OPTS) \
		--asyncio-mode=auto \
		--color=yes \
		--cov-append \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=$(COV_PACKAGE_NAME) \
		--durations=10 \
		--junitxml=junit.xml -o junit_family=legacy \
		--log-date-format="%Y-%m-%d %H:%M:%S" \
		--log-format="%(asctime)s %(levelname)s %(message)s" \
		--verbose \
		-m "not heavy_load" \
		$(CURDIR)/tests

.PHONY: "tests-ci[aiohttp]"
tests-ci[aiohttp]: _check_venv_active ## run CI tests for aiohttp only
	@pytest $(PYTEST_OPTS) \
		--asyncio-mode=auto \
		--color=yes \
		--cov-append \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=$(COV_PACKAGE_NAME) \
		--durations=10 \
		--junitxml=junit.xml -o junit_family=legacy \
		--ignore=$(CURDIR)/tests/fastapi \
		--log-date-format="%Y-%m-%d %H:%M:%S" \
		--log-format="%(asctime)s %(levelname)s %(message)s" \
		--verbose \
		-m "not heavy_load" \
		$(CURDIR)/tests

.PHONY: "tests-ci[fastapi]"
tests-ci[fastapi]: _check_venv_active ## run CI tests for fastapi only
	@pytest $(PYTEST_OPTS) \
		--asyncio-mode=auto \
		--color=yes \
		--cov-append \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=$(COV_PACKAGE_NAME) \
		--durations=10 \
		--junitxml=junit.xml -o junit_family=legacy \
		--ignore=$(CURDIR)/tests/aiohttp \
		--log-date-format="%Y-%m-%d %H:%M:%S" \
		--log-format="%(asctime)s %(levelname)s %(message)s" \
		--verbose \
		-m "not heavy_load" \
		$(CURDIR)/tests

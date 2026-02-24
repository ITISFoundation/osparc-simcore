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


#
# INSTALL TARGETS WITH EXTRAS
#

.PHONY: install-dev[all]
install-dev[all]: UV_EXTRAS = --extra aiohttp --extra fastapi
install-dev[all]: install-dev ## install dev dependencies with all extras

.PHONY: "install-dev[aiohttp]"
install-dev[aiohttp]: UV_EXTRAS = --extra aiohttp
install-dev[aiohttp]: install-dev ## install dev dependencies with aiohttp extra

.PHONY: "install-dev[fastapi]"
install-dev[fastapi]: UV_EXTRAS = --extra fastapi
install-dev[fastapi]: install-dev ## install dev dependencies with fastapi extra


.PHONY: install-ci[all]
install-ci[all]: UV_EXTRAS = --extra aiohttp --extra fastapi
install-ci[all]: install-ci ## install CI dependencies with all extras

.PHONY: "install-ci[aiohttp]"
install-ci[aiohttp]: UV_EXTRAS = --extra aiohttp
install-ci[aiohttp]: install-ci ## install CI dependencies with aiohttp extra

.PHONY: "install-ci[fastapi]"
install-ci[fastapi]: UV_EXTRAS = --extra fastapi
install-ci[fastapi]: install-ci ## install CI dependencies with fastapi extra


.PHONY: install-prod[all]
install-prod[all]: UV_EXTRAS = --extra aiohttp --extra fastapi
install-prod[all]: install-prod ## install prod dependencies with all extras

.PHONY: "install-prod[aiohttp]"
install-prod[aiohttp]: UV_EXTRAS = --extra aiohttp
install-prod[aiohttp]: install-prod ## install prod dependencies with aiohttp extra

.PHONY: "install-prod[fastapi]"
install-prod[fastapi]: UV_EXTRAS = --extra fastapi
install-prod[fastapi]: install-prod ## install prod dependencies with fastapi extra


#
# TEST TARGETS WITH EXTRAS
#

.PHONY: tests[all]
tests[all]: tests ## run tests with all extras

.PHONY: "tests[aiohttp]"
tests[aiohttp]: PYTEST_EXTRAS = --ignore=$(CURDIR)/tests/fastapi
tests[aiohttp]: tests ## run tests for aiohttp only

.PHONY: "tests[fastapi]"
tests[fastapi]: PYTEST_EXTRAS = --ignore=$(CURDIR)/tests/aiohttp
tests[fastapi]: tests ## run tests for fastapi only


.PHONY: test-ci[all]
test-ci[all]: test-ci ## run CI tests with all extras

.PHONY: "test-ci[aiohttp]"
test-ci[aiohttp]: PYTEST_EXTRAS = --ignore=$(CURDIR)/tests/fastapi
test-ci[aiohttp]: test-ci ## run CI tests for aiohttp only

.PHONY: "test-ci[fastapi]"
test-ci[fastapi]: PYTEST_EXTRAS = --ignore=$(CURDIR)/tests/aiohttp
test-ci[fastapi]: test-ci ## run CI tests for fastapi only

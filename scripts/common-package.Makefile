#
# These are common target and recipes to Makefiles for packages/
#
# USAGE: Add this in the top of package's Makefile
#
#   include ../../scripts/common.Makefile
#   include ../../scripts/common-package.Makefile
#
# OPTIONAL PROFILES (include after common-package.Makefile):
#   - For packages with optional extras (e.g., [aiohttp], [fastapi]):
#     include ../../scripts/common-package-extras.Makefile
#   - For packages with code generation or docker tasks:
#     include ../../scripts/common-package-autogen.Makefile
#
# CUSTOMIZATION: Override these variables in your Makefile:
#   - COV_PACKAGE_NAME: if coverage package name differs from PY_PACKAGE_NAME
#   - PYTEST_OPTS: additional pytest options (e.g., --keep-docker-up)
#

#
# GLOBALS
#

# NOTE $(CURDIR) in this file refers to the directory where this file is included

# Variable based on conventions (override if they do not apply)
PACKAGE_NAME        = $(notdir $(CURDIR))
PY_PACKAGE_NAME     = $(subst -,_,$(PACKAGE_NAME))
PACKAGE_VERSION     := $(shell cat VERSION)
SRC_DIR             = $(abspath $(CURDIR)/src/$(PY_PACKAGE_NAME))

# Package-specific overrides (optional)
COV_PACKAGE_NAME   ?= $(PY_PACKAGE_NAME)
PYTEST_OPTS        ?=

export PACKAGE_VERSION


#
# SHORTCUTS
#


#
# COMMON TASKS
#

.PHONY: info
info: ## displays package info
	@make --no-print-directory info-super
	# package env vars
	@echo ' PACKAGE_VERSION      : ${PACKAGE_VERSION}'
	@echo ' PY_PACKAGE_NAME      : ${PY_PACKAGE_NAME}'
	@echo ' COV_PACKAGE_NAME     : ${COV_PACKAGE_NAME}'


#
# DEPENDENCY MANAGEMENT
#

.PHONY: requirements
requirements: _check_venv_active ## compiles pip requirements (.in -> .txt) [DEPRECATED: use uv sync instead]
	@echo "ℹ️  Using pyproject.toml [dependency-groups] instead. Run: make install-dev" >&2


.PHONY: install-dev
install-dev: _check_venv_active ## install all dependencies (dev + devtools groups)
	@uv sync --active --all-groups


.PHONY: install-prod
install-prod: _check_venv_active ## install only production dependencies
	@uv sync --active --no-dev


.PHONY: install-ci
install-ci: _check_venv_active ## install CI dependencies (dev group only)
	@uv sync --active --group dev


#
# TESTING
#

.PHONY: tests
tests: _check_venv_active ## runs unit tests
	@pytest $(PYTEST_OPTS) \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=$(REPO_BASE_DIR)/.coveragerc \
		--cov-report=term-missing \
		--cov=$(COV_PACKAGE_NAME) \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--pdb \
		-vv \
		$(CURDIR)/tests


.PHONY: tests-ci
tests-ci: _check_venv_active ## runs unit tests [ci-mode]
	@pytest $(PYTEST_OPTS) \
		--asyncio-mode=auto \
		--color=yes \
		--cov-append \
		--cov-config=$(REPO_BASE_DIR)/.coveragerc \
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


#
# SUBTASKS
#

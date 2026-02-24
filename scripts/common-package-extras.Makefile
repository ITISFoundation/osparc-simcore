#
# Optional profile for packages with pyproject.toml extras
#
# USAGE: Include after common.Makefile and common-package.Makefile
#
#   include ../../scripts/common.Makefile
#   include ../../scripts/common-package.Makefile
#
#   # Define your extras and then include this profile
#   EXTRAS := extra1 extra2
#   include ../../scripts/common-package-extras.Makefile
#
# Or for packages needing custom handling, include common-package.Makefile
# and then manually define the extra targets as needed (see service-library for example).
#
# REQUIREMENTS:
# - Package must define [project.optional-dependencies] in pyproject.toml
# - This profile is optional; if not included, only basic install-dev/prod/ci targets work
#

ifndef EXTRAS
$(error EXTRAS not defined. Define in your Makefile: EXTRAS := extra1 extra2)
endif

# PYTEST_OPTS already defined in common-package.Makefile, can be overridden for this package


#
# Note: For dynamic target generation with extras, packages should explicitly define targets.
# Example for 2 extras (aiohttp, fastapi):
#
#   EXTRAS := aiohttp fastapi
#
#   .PHONY: install-dev[aiohttp]
#   install-dev[aiohttp]: _check_venv_active
#   	@uv sync --active --all-groups --extra aiohttp
#
#   .PHONY: tests[aiohttp]
#   tests[aiohttp]: _check_venv_active
#   	@pytest $(PYTEST_OPTS) ... --ignore=tests/fastapi ...
#
# This avoids make portability issues with dynamic target generation.
#

#
# Common Python test runner
#
# LIBRARY (.mk): include-only, not a directly-invoked entry point.
#
# Required variables:
# - PYTEST_COV_TARGET: package passed to pytest's --cov option
#
# Optional variables:
# - TEST_TARGET: pytest target path(s), defaults to tests/unit
# - PYTEST_ADDITIONAL_PARAMETERS: additional pytest CLI parameters
# - PYTEST_BASE_ARGS, PYTEST_ARGS_dev, PYTEST_ARGS_ci: project-specific options
#

.PHONY: FORCE

# Always out-of-date sentinel used to force pattern test targets to run.
FORCE:

TEST_TARGET ?= $(CURDIR)/tests/unit
PYTEST_ADDITIONAL_PARAMETERS ?=

PYTEST_BASE_ARGS ?=
PYTEST_ARGS_dev ?=
PYTEST_ARGS_ci ?=

_run-test-%: FORCE _check_venv_active
	# runs tests for development or CI mode
	$(if $(filter $*,dev ci),,$(error unsupported test mode '$*', expected dev or ci))
	pytest \
		$(PYTEST_BASE_ARGS) \
		$(PYTEST_ARGS_$*) \
		$(PYTEST_ADDITIONAL_PARAMETERS) \
		$(TEST_TARGET)

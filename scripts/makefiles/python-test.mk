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
# - pytest-parameters: command-line alias of the above (make "test-ci[all]"
#   pytest-parameters=--numprocesses=auto). Appended after
#   PYTEST_ADDITIONAL_PARAMETERS, so a target that sets that variable itself
#   (e.g. to pass --ignore) still receives pytest-parameters.
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

# pytest-xdist refuses to distribute tests together with --pdb (a numeric
# --numprocesses is a hard UsageError, "--numprocesses=auto" is silently
# downgraded to no parallelism), so a dev run requesting workers gets --pdb
# dropped. Evaluated at recipe time: an includer may set PYTEST_ARGS_dev either
# before or after this file.
_PYTEST_XDIST_REQUESTED := $(if $(filter -n -n% --numprocesses --numprocesses=%,$(pytest-parameters)),yes,)
_PYTEST_ARGS_dev_effective = $(if $(_PYTEST_XDIST_REQUESTED),$(filter-out --pdb,$(PYTEST_ARGS_dev)),$(PYTEST_ARGS_dev))

_run-test-%: FORCE _check_venv_active
	# runs tests for development or CI mode
	$(if $(filter $*,dev ci),,$(error unsupported test mode '$*', expected dev or ci))
	$(if $(filter dev,$*),$(if $(_PYTEST_XDIST_REQUESTED),@echo "WARNING: xdist workers requested but '--pdb' is incompatible with distributing tests: dropping --pdb for this run (single-process debugging: omit pytest-parameters)";))
	pytest \
		$(PYTEST_BASE_ARGS) \
		$(if $(filter dev,$*),$(_PYTEST_ARGS_dev_effective),$(PYTEST_ARGS_ci)) \
		$(PYTEST_ADDITIONAL_PARAMETERS) \
		$(pytest-parameters) \
		$(TEST_TARGET)

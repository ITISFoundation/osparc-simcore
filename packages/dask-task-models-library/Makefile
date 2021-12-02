#
# Targets for DEVELOPMENT of dask tasks models Library
#
include ../../scripts/common.Makefile
include ../../scripts/common-package.Makefile

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


.PHONY: tests
tests: ## runs unit tests
	# running unit tests
	@pytest -vv --color=yes --exitfirst --failed-first --durations=10 \
	--cov-config=../../.coveragerc --cov=dask_task_models_library --cov-report=term-missing \
	--pdb $(CURDIR)/tests

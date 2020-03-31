#
# Targets for DEVELOPMENT of Service Library
#
include ../../scripts/common.Makefile


.PHONY: install-dev install-prod
install-dev install-prod: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	python -m pip install $(if $(findstring dev,$@),--editable,) .


.PHONY: tests
tests: ## runs unit tests
	# running unit tests
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests

#
# Targets for DEVELOPMENT for Director service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile


.PHONY: openapi-specs
openapi-specs: ## updates and validates openapi specifications
	$(MAKE) -C $(CURDIR)/src/simcore_service_${APP_NAME}/api $@


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: openapi-specs _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	python -m pip install -r requirements/$(subst install-,,$@).txt


.PHONY: tests
tests: ## runs unit tests
	# running unit tests
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests

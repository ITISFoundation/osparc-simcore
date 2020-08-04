#
# Targets for DEVELOPMENT for Storage service
#
include ../../scripts/common.Makefile

APP_NAME := $(notdir $(CURDIR))

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


.PHONY: build build-devel
build build-devel: openapi-specs ## builds docker image (using main services/docker-compose-build.yml)
	@$(MAKE) -C ${REPO_BASE_DIR} $@ target=${APP_NAME}

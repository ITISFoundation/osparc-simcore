# osparc-simcore general makefile
#
# NOTES:
# 	- GNU make version 4.2 recommended
# 	- Use 'make -n *' to dry-run during debugging
# 	- In windows, only WSL is supported
#
# by sanderegg, pcrespov
#
include ../../scripts/common.Makefile


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	python -m pip install -r requirements/$(subst install-,,$@).txt

.PHONY: tests-unit tests-integration tests
tests-unit: ## runs unit tests
	# running unit tests
	@pytest -vv -x --ff --pdb $(CURDIR)/tests/unit


tests-integration: ## runs integration tests against local+production images
	# running integration tests local/(service):production images ...
	@export DOCKER_REGISTRY=local; \
	export DOCKER_IMAGE_TAG=production; \
	pytest -vv -x --ff --pdb $(CURDIR)/tests/integration

tests: tests-unit tests-integration ## runs all tests
	# running tests

#
# Targets for DEVELOPMENT of tests/public-api
#
include ../../scripts/common.Makefile
include ../../scripts/common-package.Makefile



.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt


# Define the files where user input will be saved
LOCUST_PARAMETERS_FILE := .locust-env.txt

test-deployment: _check_venv_active ## runs deployment test on local deploy
	@printf "$(YELLOW)Starting Locust web interface...$(NC)\n"
	locust --processes 4 --locustfile deployment_max_rps_test.py

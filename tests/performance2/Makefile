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
# Authentication credentials file
AUTH_CREDS_FILE := .auth-credentials.env

# Function to prompt for credentials if they don't exist
define prompt_for_credentials
	@if [ ! -f $(AUTH_CREDS_FILE) ]; then \
		printf "$(YELLOW)First time setup: Please enter your credentials$(NC)\n"; \
		read -p "Username: " username; \
		read -sp "Password: " password; \
		echo; \
		echo "SC_USER_NAME=$$username" > $(AUTH_CREDS_FILE); \
		echo "SC_PASSWORD=$$password" >> $(AUTH_CREDS_FILE); \
		printf "$(GREEN)Credentials saved. They won't be asked again.$(NC)\n"; \
	else \
		printf "$(GREEN)Using cached credentials from $(AUTH_CREDS_FILE)$(NC)\n"; \
	fi
endef

test-deployment: _check_venv_active ## runs deployment test on local deploy
	@$(call prompt_for_credentials)
	@printf "$(YELLOW)Starting Locust web interface...$(NC)\n"
	@export $$(cat $(AUTH_CREDS_FILE) | xargs) && \
	locust --processes 4 --locustfile deployment_max_rps_test.py

clear-credentials: ## Clear the cached authentication credentials
	@if [ -f $(AUTH_CREDS_FILE) ]; then \
		rm $(AUTH_CREDS_FILE); \
		printf "$(GREEN)Credentials cleared.$(NC)\n"; \
	else \
		printf "$(YELLOW)No credentials file found.$(NC)\n"; \
	fi

update-credentials: ## Update the cached authentication credentials
	@printf "$(YELLOW)Updating credentials:$(NC)\n"
	@read -p "Username: " username; \
	read -sp "Password: " password; \
	echo; \
	echo "SC_USER_NAME=$$username" > $(AUTH_CREDS_FILE); \
	echo "SC_PASSWORD=$$password" >> $(AUTH_CREDS_FILE); \
	printf "$(GREEN)Credentials updated successfully.$(NC)\n"

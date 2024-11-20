#
# Targets for DEVELOPMENT of tests/public-api
#
include ../../scripts/common.Makefile
include ../../scripts/common-package.Makefile

# MAIN ------------------

# Redirections to recipes in the main Makefile
.PHONY: leave build
leave build:
	$(MAKE_C) $(REPO_BASE_DIR) $@


SIMCORE_DOT_ENV = $(abspath $(CURDIR)/../../.env)

define _up_simcore
# set some parameters to allow for e2e to run
echo LOGIN_REGISTRATION_INVITATION_REQUIRED=0 >> $(SIMCORE_DOT_ENV)
echo LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=0 >> $(SIMCORE_DOT_ENV)
echo DIRECTOR_DEFAULT_MAX_NANO_CPUS=1000000000 >> $(SIMCORE_DOT_ENV)
echo DIRECTOR_DEFAULT_MAX_MEMORY=134217728 >> $(SIMCORE_DOT_ENV)
echo SIDECAR_FORCE_CPU_NODE=1 >> $(SIMCORE_DOT_ENV)
$(MAKE_C) $(REPO_BASE_DIR) up-prod ops_ci=1
endef

SERVICE_IMAGE_NAME = "sleeper"
SERVICE_VERSION = "2.1.6"
SERVICE_IMAGE_TAG = $(SERVICE_IMAGE_NAME):$(SERVICE_VERSION)

define _transfer-images-to-registry
# pushing sleeper image
@docker pull itisfoundation/$(SERVICE_IMAGE_TAG)
@docker tag itisfoundation/$(SERVICE_IMAGE_TAG) registry:5000/simcore/services/comp/itis/$(SERVICE_IMAGE_TAG)
@docker push registry:5000/simcore/services/comp/itis/$(SERVICE_IMAGE_TAG)
# completed transfer of images
@curl -s registry:5000/v2/_catalog | jq '.repositories'
@curl -s http://registry:5000/v2/simcore/services/comp/itis/$(SERVICE_IMAGE_NAME)/tags/list?n=50 | jq '.'
endef

define _give_service_access_rights
docker exec \
	$$(docker ps -q --filter="name=postgres") \
	psql --user scu --dbname simcoredb --command \
"INSERT INTO services_access_rights (key, version, gid, execute_access, write_access, product_name) \
VALUES ('simcore/services/comp/itis/$(SERVICE_IMAGE_NAME)', '$(SERVICE_VERSION)', 1, TRUE, FALSE, 'osparc');"
endef

# LOCAL ------------------

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt
	# installing playwright dependencies
	@playwright install


RETRY_DURATION_SECONDS := 30
RETRY_INTERVAL_SECONDS := 1

.PHONY: install-ci-up-simcore
install-ci-up-simcore: install-ci  ## run registry and simcore stack locally (push sleepers image and modifies DB)
	@$(MAKE_C) $(REPO_BASE_DIR) local-registry
	@$(_transfer-images-to-registry)
	@$(_up_simcore)
	@$(VENV_DIR)/bin/python utils/wait_for_services.py

	# giving access rights to images (this might take some time until the catalog is ready)
	@for ((i=0; i<$(RETRY_DURATION_SECONDS); i+=$(RETRY_INTERVAL_SECONDS))); do \
		$(_give_service_access_rights) && echo "Access rights granted successfully" && break || true; \
		echo "catalog not ready yet, retrying in ${RETRY_INTERVAL_SECONDS}..."; \
		sleep $(RETRY_INTERVAL_SECONDS); \
	done




get_my_ip := $(shell (hostname --all-ip-addresses || hostname -i) 2>/dev/null | cut --delimiter=" " --fields=1)

.PHONY: test-sleepers
test-sleepers: _check_venv_active ## runs sleepers test on local deploy
	# Note that you need a user
	@pytest \
		-sxvv \
		--color=yes \
		--pdb \
		--product-url=http://$(get_my_ip):9081 \
		--autoregister \
		--tracing=retain-on-failure \
		$(CURDIR)/tests/sleepers/test_sleepers.py


.PHONY: test-sleepers-dev
test-sleepers-dev: _check_venv_active ## runs sleepers test on local deploy
	@pytest \
		-sxvv \
		--color=yes \
		--pdb \
		--product-url=http://$(get_my_ip):9081 \
		--headed \
		--autoregister \
		$(CURDIR)/tests/sleepers/test_sleepers.py

.PHONY: test-platform
test-platform: _check_venv_active ## runs platform test on local deploy
	@pytest \
		-sxvv \
		--color=yes \
		--product-url=http://$(get_my_ip):9081 \
		--autoregister \
		--tracing=on \
		$(CURDIR)/tests/platform_CI_tests/test_platform.py

.PHONY: test-platform-dev
test-platform-dev: _check_venv_active  ## runs platform test on local deploy (with PWDEBUG=1)
	@PWDEBUG=1 pytest \
		-sxvv \
		--color=yes \
		--pdb \
		--product-url=http://$(get_my_ip):9081 \
		--headed \
		--autoregister \
		--tracing=on \
		$(CURDIR)/tests/platform_CI_tests/test_platform.py


# Define the files where user input will be saved
SLEEPERS_INPUT_FILE := .e2e-playwright-sleepers-env.txt
S4L_INPUT_FILE := .e2e-playwright-sim4life-env.txt
JUPYTER_LAB_INPUT_FILE := .e2e-playwright-jupyterlab-env.txt
CLASSIC_TIP_INPUT_FILE := .e2e-playwright-classictip-env.txt

# Prompt the user for input and store it into variables
$(SLEEPERS_INPUT_FILE) $(JUPYTER_LAB_INPUT_FILE) $(CLASSIC_TIP_INPUT_FILE) $(S4L_INPUT_FILE):
	@read -p "Enter your product URL: " PRODUCT_URL; \
	read -p "Is the product billable [y/n]: " BILLABLE; \
	read -p "Is the product lite [y/n]: " IS_LITE; \
	read -p "Is the test running in autoscaled deployment [y/n]: " AUTOSCALED; \
	read -p "Enter your username: " USER_NAME; \
	read -s -p "Enter your password: " PASSWORD; echo ""; \
	echo "--product-url=$$PRODUCT_URL --user-name=$$USER_NAME --password=$$PASSWORD" > $@; \
	if [ "$$BILLABLE" = "y" ]; then \
		echo "--product-billable" >> $@; \
	fi; \
	if [ "$$IS_LITE" = "y" ]; then \
		echo "--product-lite" >> $@; \
	fi; \
	if [ "$$AUTOSCALED" = "y" ]; then \
		echo "--autoscaled" >> $@; \
	fi; \
	if [ "$@" = "$(JUPYTER_LAB_INPUT_FILE)" ]; then \
		read -p "Enter the size of the large file (human readable form e.g. 3Gib): " LARGE_FILE_SIZE; \
		echo "--service-key=jupyter-math --large-file-size=$$LARGE_FILE_SIZE" >> $@; \
	elif [ "$@" = "$(S4L_INPUT_FILE)" ]; then \
		read -p "Do you want to check the videostreaming ? (requires to run with chrome/msedge) [y/n]: " VIDEOSTREAM; \
		if [ "$$VIDEOSTREAM" = "y" ]; then \
			echo "--check-videostreaming" >> $@; \
		fi; \
		read -p "Do you want to use the plus button (NOTE: if yes then pass the osparc-test-ID of the plus button in the service key) ? [y/n]: " PLUS_BUTTON; \
		if [ "$$PLUS_BUTTON" = "y" ]; then \
			echo "--service-key=startS4LButton" >> $@; \
			echo "--use-plus-button" >> $@; \
		else \
			read -p "Enter the service key: " SERVICE_KEY; \
			echo "--service-key=$$SERVICE_KEY" >> $@; \
		fi; \
	elif [ "$@" = "$(SLEEPERS_INPUT_FILE)" ]; then \
		read -p "Enter the number of sleepers: " NUM_SLEEPERS; \
		echo "--num-sleepers=$$NUM_SLEEPERS" >> $@; \
	fi

# Run the tests
test-sleepers-anywhere: _check_venv_active $(SLEEPERS_INPUT_FILE) ## run sleepers test and cache settings
	@$(call run_test, $(SLEEPERS_INPUT_FILE), tests/sleepers/test_sleepers.py)

test-s4l-anywhere: _check_venv_active $(S4L_INPUT_FILE) ## run s4l test and cache settings
	@$(call run_test_on_chrome, $(S4L_INPUT_FILE), tests/sim4life/test_sim4life.py)

test-jupyterlab-anywhere: _check_venv_active $(JUPYTER_LAB_INPUT_FILE) ## run jupyterlab test and cache settings
	@$(call run_test, $(JUPYTER_LAB_INPUT_FILE), tests/jupyterlabs/test_jupyterlab.py)

test-tip-anywhere: _check_venv_active $(CLASSIC_TIP_INPUT_FILE) ## run classic tip test and cache settings
	$(call run_test, $(CLASSIC_TIP_INPUT_FILE), tests/tip/test_ti_plan.py)

# Define the common test running function
define run_test
	TEST_ARGS=$$(cat $1 | xargs); \
	echo $$TEST_ARGS; \
	pytest -s $2 \
		--color=yes \
		--browser chromium \
		--headed \
		$$TEST_ARGS
endef

define run_test_on_chrome
	TEST_ARGS=$$(cat $1 | xargs); \
	echo $$TEST_ARGS; \
	pytest -s $2 \
		--color=yes \
		--browser-channel chrome \
		--headed \
		$$TEST_ARGS
endef

clean:
	-@rm -rf $(SLEEPERS_INPUT_FILE) $(JUPYTER_LAB_INPUT_FILE) $(CLASSIC_TIP_INPUT_FILE)

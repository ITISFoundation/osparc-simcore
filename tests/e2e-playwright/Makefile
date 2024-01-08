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
echo DEFAULT_MAX_NANO_CPUS=1000000000 >> $(SIMCORE_DOT_ENV)
echo DEFAULT_MAX_MEMORY=134217728 >> $(SIMCORE_DOT_ENV)
echo SIDECAR_FORCE_CPU_NODE=1 >> $(SIMCORE_DOT_ENV)
$(MAKE_C) $(REPO_BASE_DIR) up-prod ops_ci=1
endef

define _transfer-images-to-registry
# pushing sleeper image
@docker pull itisfoundation/sleeper:1.0.0
@docker tag itisfoundation/sleeper:1.0.0 registry:5000/simcore/services/comp/itis/sleeper:1.0.0
@docker push registry:5000/simcore/services/comp/itis/sleeper:1.0.0
# completed transfer of images
@curl -s registry:5000/v2/_catalog | jq '.repositories'
@curl -s http://registry:5000/v2/simcore/services/comp/itis/sleeper/tags/list?n=50 | jq '.'
endef


# LOCAL ------------------

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt
	# installing playwright dependencies
	@playwright install

install-ci-up-simcore: install-ci
	@$(MAKE_C) $(REPO_BASE_DIR) local-registry
	@$(_up_simcore)
	@$(VENV_DIR)/bin/python utils/wait_for_services.py
	@$(_transfer-images-to-registry)


get_my_ip := $(shell hostname --all-ip-addresses | cut --delimiter=" " --fields=1)

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
		$(CURDIR)/tests/sleepers/sleepers.py


.PHONY: test-sleepers-dev
test-sleepers-dev: _check_venv_active ## runs sleepers test on local deploy
	@pytest \
		-sxvv \
		--color=yes \
		--pdb \
		--product-url=http://$(get_my_ip):9081 \
		--headed \
		--autoregister \
		$(CURDIR)/tests/sleepers/sleepers.py



.PHONY: test-dev
test-dev: ## runs tests with --keep-docker-up, --pdb and --ff
	# WARNING:
	#   - do not forget to build latest changes images
	#   - this test can be affected by existing docker volumes in your host machine
	#
	# running unit tests
	@pytest --keep-docker-up \
	-vv \
	--color=yes \
	--failed-first \
	--durations=10 \
	--asyncio-mode=auto \
	--pdb \
	$(CURDIR)


.PHONY: test-ci
test-ci: ## runs ci tests (i.e. w/o debug tools and with code coverage)
	@pytest \
	-vv \
	--color=yes \
	--durations=10 \
	$(CURDIR)

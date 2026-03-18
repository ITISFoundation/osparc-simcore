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

# LOCAL ------------------

SIMCORE_DOT_ENV = $(abspath $(CURDIR)/../../.env)

define _up_simcore
@$(MAKE_C) $(REPO_BASE_DIR) .env
# DISABLED: test setup has no otl service
echo TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT=null >> $(SIMCORE_DOT_ENV)
echo TRACING_OPENTELEMETRY_COLLECTOR_PORT=null >> $(SIMCORE_DOT_ENV)
@$(MAKE_C) $(REPO_BASE_DIR) local-registry
@$(MAKE_C) $(REPO_BASE_DIR) up-prod-phased $(if $(filter install-ci,$@),ops_ci=1,)
endef

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt
	@$(_up_simcore)
	@$(REPO_BASE_DIR)/tests/utils/wait_for_services.py


.PHONY: test-dev
test-dev: ## runs tests with debug tools
	# WARNING:
	#   - do not forget to build latest changes images
	#   - this test can be affected by existing docker volumes in your host machine
	#
	# running unit tests
	@pytest \
	--pdb \
	--failed-first \
	-s \
	--log-cli-level=DEBUG \
	-vv \
	--color=yes \
	--durations=10 \
	--asyncio-mode=auto \
	--keep-docker-up \
	$(CURDIR)


.PHONY: test-ci
test-ci: ## runs ci tests (i.e. w/o debug tools)
	@pytest \
	-vv \
	--color=yes \
	--durations=10 \
	--asyncio-mode=auto \
	--keep-docker-up \
	$(CURDIR)

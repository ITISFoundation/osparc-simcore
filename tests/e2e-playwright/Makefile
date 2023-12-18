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

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt
	# installing playwright dependencies
	@playwright install


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
		$(CURDIR)/tests/sleepers.py


.PHONY: test-sleepers-dev
test-sleepers-dev: _check_venv_active ## runs sleepers test on local deploy
	@pytest \
		-sxvv \
		--color=yes \
		--pdb \
		--product-url=http://$(get_my_ip):9081 \
		--headed \
		--autoregister \
		$(CURDIR)/tests/sleepers.py



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

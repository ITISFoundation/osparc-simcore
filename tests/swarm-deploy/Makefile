#
# Targets for DEVELOPMENT for system tests
#
include ../../scripts/common.Makefile


.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install install-dev install-prod install-ci

install:  install-ci

install-dev install-prod install-ci: _check_venv_active ## install requirements in dev/prod/ci mode
	# installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt


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
test-ci: export CI=true
test-ci: ## runs ci tests (i.e. w/o debug tools)
	@pytest \
	-vv \
	--color=yes \
	--durations=10 \
	--asyncio-mode=auto \
	--keep-docker-up \
	$(CURDIR)

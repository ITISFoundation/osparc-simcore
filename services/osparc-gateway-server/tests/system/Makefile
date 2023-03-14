#
# Targets for DEVELOPMENT for system tests
#
include ../../../../scripts/common.Makefile


.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install install-dev install-prod install-ci

install:  install-ci

install-dev install-prod install-ci: _check_venv_active ## install requirements in dev/prod/ci mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


.PHONY: tests
tests: _check_venv_active ## runs all tests [CI]
	# running system tests
	pytest \
		--asyncio-mode=auto \
		--color=yes \
		--durations=10 \
		-vv \
		$(CURDIR)

.PHONY: test-dev
tests-dev: _check_venv_active ## runs all tests [DEV]
	# running system tests
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--keep-docker-up \
		--pdb \
		-vv \
		$(CURDIR)

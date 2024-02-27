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


.PHONY: tests
tests: _check_venv_active ## runs all tests [DEV]
	# running unit tests
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--pdb \
		-vv \
		$(CURDIR)

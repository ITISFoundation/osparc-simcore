#
# Targets for DEVELOPMENT of tests/public-api
#
include ../../scripts/common.Makefile
include ../../scripts/common-package.Makefile

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


.PHONY: test-dev
test-dev: ## runs tests with --keep-docker-up, --pdb and --ff
	# running unit tests
	@pytest --keep-docker-up \
	-vv \
	--color=yes \
	--exitfirst --failed-first \
	--durations=10 \
	--pdb \
	$(CURDIR)

#
# Targets for DEVELOPMENT of common Library
#
include ../../scripts/common.Makefile
include ../../scripts/common-package.Makefile

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt


.PHONY: tests tests-ci
tests: ## runs unit tests
	# running unit tests
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov=common_library \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--pdb \
		-vv \
		$(CURDIR)/tests

tests-ci: ## runs unit tests [ci-mode]
	# running unit tests
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-append \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=common_library \
		--durations=10 \
		--log-date-format="%Y-%m-%d %H:%M:%S" \
    --log-format="%(asctime)s %(levelname)s %(message)s" \
    --verbose \
    -m "not heavy_load" \
		$(CURDIR)/tests

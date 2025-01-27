#
# Targets for DEVELOPMENT of Service Library
#
include ../../scripts/common.Makefile

help:	## overwrites and calls common help function
	$(MAKE) --no-print-directory --file ../../scripts/common.Makefile $@
	@echo
	@echo '🚨 BEWARE there are issues with brakets in names `make test-dev[aiohttp]` will raise errors:'
	@echo '✅` `make "test-dev[aiohttp]"` works as intended'
	@echo '👓 Please note: when INSTALLING, DEVELOPING and TESTING '
	@echo
	@echo 'servicelib support for aiohttp extras is not included:'
	@echo '- `make install-dev`: common features w/o any extras'
	@echo '- `make "install-dev[aiohttp]"`: w/ aiohttp extras'
	@echo '- `make "install-dev[fastapi]"`: w/ fastapi extras'
	@echo '- `make "install-dev[all]"`: w/ all extras'


.PHONY: "install-dev" "install-dev[aiohttp]" "install-dev[fastapi]" "install-dev[all]"
.PHONY: "install-ci" "install-ci[aiohttp]" "install-ci[fastapi]" "install-ci[all]"

install-%: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt

APP_PACKAGE_NAME=servicelib
.PHONY: test-dev
test-dev: ## runs unit tests in w/o extras
	# running test-dev
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=$(CURDIR)/../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--junitxml=junit.xml -o junit_family=legacy \
		--cov=$(APP_PACKAGE_NAME) \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--keep-docker-up \
		--ignore=tests/aiohttp \
		--ignore=tests/fastapi \
		--pdb \
		-vv \
		$(CURDIR)/tests


.PHONY: test-dev[aiohttp]
test-dev[aiohttp]: ## runs unit common tests and aiohttp extras
	# running test-dev[aiohttp]
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=$(CURDIR)/../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--junitxml=junit.xml -o junit_family=legacy \
		--cov=$(APP_PACKAGE_NAME) \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--keep-docker-up \
		--ignore=tests/fastapi \
		--pdb \
		-vv \
		$(CURDIR)/tests

.PHONY: test-dev[fastapi]
test-dev[fastapi]: ## runs unit common tests and fastapi extras
	# running test-dev[aiohttp]
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=$(CURDIR)/../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--junitxml=junit.xml -o junit_family=legacy \
		--cov=$(APP_PACKAGE_NAME) \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--keep-docker-up \
		--ignore=tests/aiohttp \
		--pdb \
		-vv \
		$(CURDIR)/tests

.PHONY: test-dev[all]
test-dev[all]: ## runs unit tests  w/ all extras
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=$(CURDIR)/../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--junitxml=junit.xml -o junit_family=legacy \
		--cov=$(APP_PACKAGE_NAME) \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--keep-docker-up \
		--pdb \
		-vv \
		$(CURDIR)/tests


.PHONY: test-ci[all]
test-ci[all]:  ## runs unit tests  w/ all extras
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-append \
		--cov-config=$(CURDIR)/../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=$(APP_PACKAGE_NAME) \
		--durations=10 \
		--junitxml=junit.xml -o junit_family=legacy \
		--keep-docker-up \
		--log-date-format="%Y-%m-%d %H:%M:%S" \
		--log-format="%(asctime)s %(levelname)s %(message)s" \
		--verbose \
		-m "not heavy_load" \
		--log-cli-level=DEBUG \
		$(CURDIR)/tests

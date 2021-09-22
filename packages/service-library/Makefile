#
# Targets for DEVELOPMENT of Service Library
#
include ../../scripts/common.Makefile

help:	## overwrites and calls common help function
	$(MAKE) --no-print-directory --file ../../scripts/common.Makefile $@
	@echo
	@echo '🚨 BEWARE there are issues with brakets in names `make test[aiohttp]` will raise errors:'
	@echo '✅` `make "test[aiohttp]"` works as intended'
	@echo '👓 Please note: when INSTALLING, DEVELOPING and TESTING '
	@echo
	@echo 'servicelib support for aiohttp extras is not included:'
	@echo '- `make install-dev`: common features w/o any extras'
	@echo '- `make "install-dev[aiohttp]"`: w/ aiohttp extras'
	@echo '- `make "install-dev[fastapi]"`: w/ fastapi extras'
	@echo '- `make "install-dev[all]"`: w/ all extras'


.PHONY: install-dev install-dev[aiohttp] install-dev[fastapi] install-ci install-ci[aiohttp] install-ci[fastapi]
install-dev install-dev[aiohttp] install-dev[fastapi] install-ci install-ci[aiohttp] install-ci[fastapi]: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


.PHONY: test-dev
test-dev: ## runs unit tests in w/o extras
	# running test-dev
	@pytest -vv --exitfirst --failed-first --durations=10\
	--pdb \
	--ignore=tests/aiohttp --ignore=tests/fastapi \
	$(CURDIR)/tests

.PHONY: test-dev[aiohttp]
test-dev[aiohttp]: ## runs unit common tests and aiohttp extras
	# running test-dev[aiohttp]
	@pytest -vv --exitfirst --failed-first --durations=10\
	--pdb \
	--ignore=tests/fastapi \
	$(CURDIR)/tests

.PHONY: test-dev[aiohttp]
test-dev[fastapi]: ## runs unit common tests and fastapi extras
	# running test-dev[aiohttp]
	@pytest -vv --exitfirst --failed-first --durations=10\
	--pdb \
	--ignore=tests/aiohttp \
	$(CURDIR)/tests


.PHONY: tests
tests: ## runs unit tests in w/o aiohttp extras
	# running tests
	@pytest -vv --color=yes --exitfirst --failed-first --durations=10 \
	--cov-config=../../.coveragerc --cov=servicelib --cov-report=term-missing \
	--ignore=tests/aiohttp --ignore=tests/fastapi \
	$(CURDIR)/tests


.PHONY: tests[aiohttp]
tests[aiohttp]: ## runs unit tests and aiohttp extras
	# running tests[aiohttp]
	@pytest -vv --color=yes --exitfirst --failed-first --durations=10 \
	--cov-config=../../.coveragerc --cov=servicelib --cov-report=term-missing \
	--ignore=tests/fastapi \
	$(CURDIR)/tests


.PHONY: tests[fastapi]
tests[fastapi]: ## runs unit tests and fastapi extras
	# running tests[fastapi]
	@pytest -vv --color=yes --exitfirst --failed-first --durations=10 \
	--cov-config=../../.coveragerc --cov=servicelib --cov-report=term-missing \
	--ignore=tests/aiohttp \
	$(CURDIR)/tests

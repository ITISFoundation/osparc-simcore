#
# Targets for DEVELOPMENT of Service Library
#
include ../../scripts/common.Makefile

help:	## overwrites and calls common help function
	$(MAKE) -f ../../scripts/common.Makefile $@
	@echo '🚨 BEWARE there are issues with brakets in names `make test[aiohttp]` will raise errors:'
	@echo '✅` `make "test[aiohttp]"` works as intended'
	@echo '👓 Please note: when INSTALLING, DEVELOPING and TESTING '
	@echo 'servicelib support for aiohttp extras is not included:'
	@echo '- `make install-dev`: without aiohttp extras'
	@echo '- `make "install-dev[aiohttp]"`: with aiohttp extras'
    
.PHONY: install-dev install-dev[aiohttp] install-ci install-ci[aiohttp]
install-dev install-dev[aiohttp] install-ci install-ci[aiohttp]: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


.PHONY: test-dev
test-dev: ## runs unit tests in without aiohtto extras
	# running test-dev
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb --ignore=tests/aiohttp $(CURDIR)/tests

.PHONY: test-dev[aiohttp]
test-dev[aiohttp]: ## runs unit tests and aiohtto extras
	# running test-dev[aiohttp]
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests

.PHONY: tests
tests: ## runs unit tests in without aiohtto extras
	# running tests
	@pytest -vv --color=yes --exitfirst --failed-first --durations=10 \
	--cov-config=../../.coveragerc --cov=servicelib --cov-report=term-missing \
	--pdb --ignore=tests/aiohttp $(CURDIR)/tests

.PHONY: tests[aiohttp]
tests[aiohttp]: ## runs unit tests and aiohtto extras
	# running tests[aiohttp]
	@pytest -vv --color=yes --exitfirst --failed-first --durations=10 \
	--cov-config=../../.coveragerc --cov=servicelib --cov-report=term-missing \
	--pdb $(CURDIR)/tests


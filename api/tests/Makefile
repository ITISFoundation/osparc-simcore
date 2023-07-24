.DEFAULT_GOAL := help

UPGRADE_OPTION := $(if $(upgrade),--upgrade-package $(upgrade),--upgrade)


.PHONY: all
all: install test-dev

.PHONY: reqs
requirements.txt: requirements.in
	# pip compiling $<
	pip-compile $(UPGRADE_OPTION) \
		--build-isolation \
		--strip-extras \
		--resolver=backtracking \
		--output-file $@ $<
reqs: requirements.txt ## alias to compile requirements.txt


.PHONY: install
install: _check_venv_active requirements.txt ## installs dependencies
	# installing requirements
	pip-sync requirements.txt


.PHONY: test-dev
test-dev: _check_venv_active ## runs all tests [DEV]
	# running unit tests
	pytest -vv --exitfirst --failed-first  --durations=10 --pdb $(CURDIR)



.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for tests/swarm-deploy:"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""


.PHONY: _check_venv_active
_check_venv_active:
	# checking whether virtual environment was activated
	@python3 -c "import sys; assert sys.base_prefix!=sys.prefix"

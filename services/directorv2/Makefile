.DEFAULT_GOAL := help

.PHONY: help
help: ## display this message
	@awk 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: _ensure-in-venv
_ensure-in-venv:
	@python3 -c "import os; os.environ['VIRTUAL_ENV']" || (echo "\n>>>> You are not in a virtualenv. Activate one <<<<\n"; exit 1)

.PHONY: install-dev-dependencies
install-dev-dependencies: _ensure-in-venv ## install dev tools
	@pip install \
		pip-tools \
		black \
		rope

.PHONY: compile-dependencies
compile-dependencies: _ensure-in-venv ## snapshot test & package dependencies
	@pip-compile --build-isolation director/requirements/base.in --output-file director/requirements/base.txt 
	@pip-compile --build-isolation director/requirements/test.in --output-file director/requirements/test.txt 

.PHONY: install-test-dependencies
install-test-dependencies: _ensure-in-venv ## install package test dependencies
	@cd director/requirements; pip-sync test.txt 

.PHONY: tests
tests: _ensure-in-venv ## run the test suite
	@tox -r -c director/tox.ini

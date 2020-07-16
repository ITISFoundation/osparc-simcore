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
		rope \
		tox

.PHONY: compile-dependencies
compile-dependencies: _ensure-in-venv ## snapshot test & package dependencies
	@pip-compile --build-isolation requirements/base.in --output-file requirements/base.txt
	@pip-compile --build-isolation requirements/test.in --output-file requirements/test.txt

.PHONY: tox-full-recreate
tox-full-recreate: _ensure-in-venv ## runs all tools in tox in a new environemtn
	@tox -r

.PHONY: tox-full
tox-full: _ensure-in-venv ## runs all tools in tox in cached environment
	@tox

.PHONY: tox-tests
tox-tests: _ensure-in-venv ## run only tests from tox
	@tox -e py38

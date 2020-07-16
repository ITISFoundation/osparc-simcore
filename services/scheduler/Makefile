include ../../scripts/common.Makefile

APP_NAME := $(notdir $(CURDIR))

.DEFAULT_GOAL := help

.PHONY: help
help: ## display this message
	@awk 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: _ensure-in-venv
_ensure-in-venv:
	@python3 -c "import os; os.environ['VIRTUAL_ENV']" || (echo "\n>>>> You are not in a virtualenv. Activate one <<<<\n"; exit 1)

.PHONY: reqs
reqs: _ensure-in-venv ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs

.PHONY: compile-dependencies
compile-dependencies: _ensure-in-venv ## snapshot test & package dependencies
	@pip-compile --build-isolation requirements/base.in --output-file requirements/base.txt
	@pip-compile --build-isolation requirements/test.in --output-file requirements/test.txt

.PHONY: tox-full-recreate
tox-full-recreate: _ensure-in-venv ## runs all tools in tox in a new environment
	@tox -r

.PHONY: tox-full
tox-full: _ensure-in-venv ## runs all tools in tox in cached environment
	@tox

.PHONY: tox-tests
tox-tests: _ensure-in-venv ## run only tests from tox cached environment
	@tox -e py38

.PHONY: tox-ci-pylint
tox-ci-pylint: _ensure-in-venv ## runs pylint in a new enviornment
	@tox -r -e pylint

.PHONY: tox-ci-mypy
tox-ci-mypy: _ensure-in-venv ## runs mypy in a new enviornment
	@tox -r -e mypy

.PHONY: tox-ci-tests
tox-ci-tests: _ensure-in-venv ## runs tests with coverage in a new enviornment
	@tox -r -e py38,report

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
	@pip-compile --build-isolation requirements/_base.in --output-file requirements/_base.txt
	@pip-compile --build-isolation requirements/_test.in --output-file requirements/_test.txt

.PHONY: install-dev-dependencies
install-dev-dependencies: _ensure-in-venv ## snapshot test & package dependencies
	@pip install -r requirements/_base.txt

.PHONY: tox-full-recreate
tox-full-recreate: _ensure-in-venv ## runs all tools in tox in a new environment
	@tox -r -p

.PHONY: tox-full
tox-full: _ensure-in-venv ## runs all tools in tox in cached environment
	@tox -p

.PHONY: tox-tests
tox-tests: _ensure-in-venv ## run only tests from tox cached environment
	@tox -e py38

.PHONY: tox-tests-recreate
tox-tests-recreate: _ensure-in-venv ## run only tests from tox in a new environment
	@tox -r -e py38

.PHONY: tox-isort
tox-isort: _ensure-in-venv ## applies isort to all project files
	@tox -e isort

.PHONY: ci-tox-pylint
ci-tox-pylint: ## runs pylint in a new enviornment
	@tox -r -e pylint

.PHONY: ci-tox-mypy
ci-tox-mypy: ## runs mypy in a new enviornment
	@tox -r -e mypy

.PHONY: ci-tox-tests
ci-tox-tests: ## runs tests with coverage in a new enviornment
	@tox -r -e py38,report

.PHONY: ci-install-requirements
ci-install-requirements: ## runs tests with coverage in a new enviornment
	@pip install -r requirements/dev.txt

.PHONY: run-github-action-locally
run-github-action-locally:  ## runs the defined github action from the workflow locally
	# Note: ⚡ act is required https://github.com/nektos/act
	# Note: ⚠️  "act-environments-ubuntu:18.04" image is 18Gb takes a lot the first time
	@act -C ../../. -P ubuntu-18.04=nektos/act-environments-ubuntu:18.04 -j unit-test-scheduler

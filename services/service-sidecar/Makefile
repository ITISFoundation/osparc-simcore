include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

APP_NAME := $(notdir $(CURDIR))

.DEFAULT_GOAL := help


.PHONY: _ensure-in-venv
_ensure-in-venv:
	@python3 -c "import os; os.environ['VIRTUAL_ENV']" || (echo "\n>>>> You are not in a virtualenv. Activate one <<<<\n"; exit 1)

.PHONY: install-dev-dependencies
install-dev-dependencies: _ensure-in-venv ## install depenencies for development
	@pip install -r requirements/_base.txt

.PHONY: install-dev-dependencies
install-dev-dependencies: _ensure-in-venv ## install depenencies for development
	@pip install -r requirements/_base.txt

.PHONY: dev-run
dev-run: _ensure-in-venv ## starts the container on its own
	@docker run -it --rm \
			-p 8000:8000 \
			-v $(CURDIR):/devel/services/service-sidecar \
			local/service-sidecar:development

.PHONY: ci-tox-codestyle
ci-tox-codestyle: ## runs codestyle checks
	@tox -r -e codestyle

.PHONY: ci-tox-tests
ci-tox-tests: ## runs tests with coverage in a new enviornment
	@tox -r -e py36,report

.PHONY: ci-install-requirements
ci-install-requirements: ## runs tests with coverage in a new enviornment
	@pip install -r requirements/dev.txt
	@pip install tox

.PHONY: run-github-action-locally
run-github-action-locally:  ## runs the defined github action from the workflow locally
	# Note: ⚡ act is required https://github.com/nektos/act
	@act -C ../../. -P ubuntu-20.04=catthehacker/ubuntu:act-20.04 -j unit-test-service-sidecar

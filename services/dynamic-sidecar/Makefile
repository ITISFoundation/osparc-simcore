include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

APP_NAME := $(notdir $(CURDIR))

.DEFAULT_GOAL := help


.PHONY: codestyle
codestyle: ## enforces codestyle and runs pylint and mypy
	isort setup.py src/simcore_service_dynamic_sidecar tests
	black src/simcore_service_dynamic_sidecar tests/
	pylint --rcfile=../../.pylintrc src/simcore_service_dynamic_sidecar tests/
	mypy src/simcore_service_dynamic_sidecar tests/ --ignore-missing-imports


.PHONY: run-github-action-locally
run-github-action-locally:  ## runs the defined github action from the workflow locally
	# Note: ⚡ act is required https://github.com/nektos/act
	@act -C ../../. -P ubuntu-20.04=catthehacker/ubuntu:act-20.04 -j unit-test-dynamic-sidecar

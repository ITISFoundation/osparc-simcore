include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile
include ../../scripts/common-service-fastapi.Makefile


.DEFAULT_GOAL := help


.PHONY: run-github-action-locally
run-github-action-locally:  ## runs "unit-test-dynamic-sidecar" defined int github workflow locally
	@make github-workflow-job job=unit-test-dynamic-sidecar

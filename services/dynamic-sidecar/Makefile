include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile



.PHONY: openapi-specs openapi.json
openapi-specs: openapi.json
openapi.json: .env ## Creates OAS document openapi.json
	# generating openapi specs file under $<
	@set -o allexport; \
	source .env; \
	set +o allexport; \
	simcore-service-dynamic-sidecar openapi > $@



.PHONY: run-github-action-locally
run-github-action-locally:  ## runs "unit-test-dynamic-sidecar" defined int github workflow locally
	@make github-workflow-job job=unit-test-dynamic-sidecar

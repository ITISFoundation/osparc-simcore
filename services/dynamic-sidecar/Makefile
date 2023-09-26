include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

.DEFAULT_GOAL := help


.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)




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

# WARNING: tmp using --no-build-isolation due to: https://github.com/yaml/pyyaml/issues/724#issuecomment-1638636728
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# Installing in $(subst install-,,$@) mode
	pip-sync \
		--pip-args --no-build-isolation \
		requirements/$(subst install-,,$@).txt

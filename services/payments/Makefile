#
# DEVELOPMENT recipes for payments
#
.DEFAULT_GOAL := help

include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/service.mk


ENV_IGNORE_FLAGS := --auto-password

.PHONY: openapi.json
openapi-specs: openapi.json
openapi.json: .env-ignore ## produces openapi.json
	$(call generate_and_validate_openapi,$<,$@)


# NOTE: Create using `ln -s path/to/osparc-config/repo.config .env-secret`
external ?= .env-secret

test-dev-unit-external: ## runs test-dev against external service defined in $(external) envfile
	# Running tests using external environ '$(external)'
	$(MAKE) test-dev-unit pytest-parameters="--external-envfile=$(external) -m can_run_against_external"

test-ci-unit-external: ## runs test-ci against external service defined in $(external) envfile
	# Running tests using external environ '$(external)'
	$(MAKE) test-ci-unit pytest-parameters="--external-envfile=$(external) -m can_run_against_external"


test-repo-config: ## runs validation against `repo.config` files. e.g. `make test-repo-config SEARCH_ROOT=/path/to/ospar-config/deployments`
	@if [ -z "$(SEARCH_ROOT)" ]; then \
	    echo "Error: SEARCH_ROOT is not set. Please set SEARCH_ROOT to the directory with repo.config files"; \
	    exit 1; \
	fi
	@for file in $$(find $(SEARCH_ROOT) -type f -name 'repo.config'); do \
	    echo "Validating settings for $$file"; \
	    pytest --external-envfile="$$file" --pdb tests/unit/test_core_settings.py; \
	done

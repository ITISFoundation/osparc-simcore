#
# DEVELOPMENT recipes for payments
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile


.env-ignore:
	$(APP_CLI_NAME) echo-dotenv --auto-password > $@

.PHONY: openapi.json
openapi-specs: openapi.json
openapi.json: .env-ignore ## produces openapi.json
	# generating openapi specs file (need to have the environment set for this)
	@set -o allexport; \
	source $<; \
	set +o allexport; \
	python3 -c "import json; from $(APP_PACKAGE_NAME).main import *; print( json.dumps(app_factory().openapi(), indent=2) )" > $@


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

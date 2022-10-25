#
# DEVELOPMENT recipes for datcore-adapter
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile


# Check that given variables are set and all have non-empty values,
# die with an error otherwise.
#
# Params:
#   1. Variable name(s) to test.
#   2. (optional) Error message to print.
guard-%:
	@ if [ "${${*}}" = "" ]; then \
		echo "Environment variable $* not set"; \
		exit 1; \
	fi

test-dev-unit-real-pennsieve: guard-api-key guard-api-secret guard-dataset-id guard-collection-id guard-package-id ## test against real pennsieve server providing necessary credentials
	$(MAKE) test-dev-unit \
					pytest-parameters="--api-key=$(api-key) --api-secret=$(api-secret) --dataset=$(dataset-id) --collection=$(collection-id) --file=$(package-id)"

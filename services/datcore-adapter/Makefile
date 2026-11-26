#
# DEVELOPMENT recipes for datcore-adapter
#
.DEFAULT_GOAL := help

include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/service.mk


test-dev-unit-real-pennsieve: guard-api-key guard-api-secret guard-dataset-id guard-collection-id guard-package-id ## test against real pennsieve server providing necessary credentials
	$(MAKE) test-dev-unit \
					pytest-parameters="--api-key=$(api-key) --api-secret=$(api-secret) --dataset=$(dataset-id) --collection=$(collection-id) --file=$(package-id)"

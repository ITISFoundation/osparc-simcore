#
# Targets for DEVELOPMENT for Storage service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile


.PHONY: openapi-specs
openapi-specs: ## updates and validates openapi specifications
	$(MAKE) -C $(CURDIR)/src/simcore_service_${APP_NAME}/api $@


.PHONY: tests
tests: ## runs unit tests
	# running unit tests
	@pytest -vv --asyncio-mode=auto --failed-first --durations=10 --pdb $(CURDIR)/tests


# DEVELOPMENT ########
.env:
	cp .env-devel $@

run-devel: .env
	# start app (within $<) in prod mode
	export $(shell grep -v '^#' .env-devel | xargs -0); \
	$(APP_CLI_NAME)

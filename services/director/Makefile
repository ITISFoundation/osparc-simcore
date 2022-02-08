#
# Targets for DEVELOPMENT for Director service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile


_check_python_version:
	# Checking that runs with correct python version
	@python3 -c "import sys; current_version=[int(d) for d in '3.6'.split('.')]; assert sys.version_info[:2]==tuple(current_version[:2]), f'Expected python $(EXPECTED_PYTHON_VERSION), got {sys.version_info}'"


.PHONY: openapi-specs
openapi-specs: ## updates and validates openapi specifications
	$(MAKE) -C $(CURDIR)/src/simcore_service_${APP_NAME}/api $@

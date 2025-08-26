#
# DEVELOPMENT recipes for resource-usage-tracker
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile



.PHONY: openapi.json
openapi-specs: openapi.json
openapi.json:  ## produces openapi.json
	# generating openapi specs file (need to have the environment set for this)
	@python3 -c "import json; from $(APP_PACKAGE_NAME).main import *; print( json.dumps(app_factory().openapi(), indent=2) )" > $@

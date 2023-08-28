#
# DEVELOPMENT recipes for payments
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile


.env:
	$(APP_CLI_NAME) generate-dotenv --auto-password > $@

.PHONY: openapi.json
openapi-specs: openapi.json
openapi.json: .env ## produces openapi.json
	# generating openapi specs file (need to have the environment set for this)
	@set -o allexport; \
	source .env; \
	set +o allexport; \
	python3 -c "import json; from $(APP_PACKAGE_NAME).main import *; print( json.dumps(the_app.openapi(), indent=2) )" > $@

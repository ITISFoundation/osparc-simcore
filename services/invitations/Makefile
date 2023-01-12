#
# DEVELOPMENT recipes for invitations
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile



.env:
	$(APP_CLI_NAME) generate-dotenv > $@


.PHONY: openapi.json
openapi-specs: openapi.json
openapi.json: .env ## produces openapi.json
	# generating openapi specs file (need to have the environment set for this)
	@set -o allexport; \
	source .env; \
	set +o allexport; \
	python3 -c "import json; from $(APP_PACKAGE_NAME).web_main import *; print( json.dumps(the_app.openapi(), indent=2) )" > $@




run: .env build ## runs (development)
	docker run -it --env-file .env -p 8000:8000 local/$(APP_NAME):production $(APP_CLI_NAME) serve

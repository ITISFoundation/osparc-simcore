#
# Targets for DEVELOPMENT for Director service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

.PHONY: openapi-specs
openapi-specs: .env ## generates openapi specs file under src/simcore_service_director/api/vX/openapi.json
	# generating openapi specs file (need to have the environment set for this)
	@set -o allexport; \
	source .env; \
	set +o allexport; \
	python3 -c "import json; from $(APP_PACKAGE_NAME).main import app_factory; print(json.dumps(app_factory().openapi(), indent=2))" > ./src/$(APP_PACKAGE_NAME)/api/v0/openapi.json

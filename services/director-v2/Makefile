#
# DEVELOPMENT recipes for director-v2
#


include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

.PHONY: requirements reqs
requirements reqs: ## (or reqs) compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: openapi.json
openapi-specs: openapi.json
openapi.json: .env
	# generating openapi specs file (need to have the environment set for this)
	@set -o allexport; \
	source .env; \
	set +o allexport; \
	python3 -c "import json; from $(APP_PACKAGE_NAME).main import *; print( json.dumps(the_app.openapi(), indent=2) )" > $@


DOCKER_API_VERSION ?= 1.41
.PHONY: directorv2_rest_api_schemas.py
directorv2_rest_api_schemas.py: openapi.json ## auto-generates pydantic models for Docker REST API models
	# auto-generates $@ from $<
	$(SCRIPTS_DIR)/openapi-pydantic-models-generator.bash \
			--input $< \
			--output $@ \
			--field-constraints \
			--reuse-model \
			--enum-field-as-literal=all

	# formats
	@black $@
	# copy output to src/models_library/generated_models...
	@mv $@ $(PACKAGES_DIR)/models-library/src/models_library/generated_models/$@
	# done

# DEVELOPMENT #############
include .env

REGISTRY_NAMESPACE=$(subst http://,,${REGISTRY_URL})

.env:
	# Copying makefile from .env-devel
	@cp .env-devel $@


.PHONY: up-extra down down-extra run-devel

up-extra: .env down # starts pg stack fixture
	# resolving $@ under environ $<
	docker compose -f docker-compose-extra.yml config
	# starting database stack as defined in  ...
	docker compose -f docker-compose-extra.yml up --detach


down down-extra:  ## stops extra stack
	# stopping extra services
	-@docker compose -f docker-compose-extra.yml down



run-devel: .env up-extra  ## starts app with extra stack
	# start app (within $<) in devel mode
	uvicorn $(APP_PACKAGE_NAME).__main__:the_app \
		--reload --reload-dir $(SRC_DIR) \
		--port=8000 --host=0.0.0.0

run-prod: .env up-extra
	# start app (within $<) in prod mode
	$(APP_CLI_NAME)


.PHONY: transfer-images-to-registry
transfer-images-to-registry: .env ## transfer images to registry
	# pushing sleeper image
	@docker pull itisfoundation/sleeper:1.0.0
	@docker tag itisfoundation/sleeper:1.0.0 $(REGISTRY_NAMESPACE)/simcore/services/comp/itis/sleeper:1.0.0
	@docker push $(REGISTRY_NAMESPACE)/simcore/services/comp/itis/sleeper:1.0.0
	# completed transfer of images
	$(MAKE) info-registry


.PHONY: info-registry
info-registry: .env ## displays content of docker-registry
	# ${REGISTRY_URL} info queries
	curl -s ${REGISTRY_URL}/v2/_catalog | jq '.repositories'
	curl -s ${REGISTRY_URL}/v2/simcore/services/comp/itis/sleeper/tags/list?n=50 | jq '.'

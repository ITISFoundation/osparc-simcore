#
# DEVELOPMENT recipes for director-v2
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile


.PHONY: requirements reqs
requirements reqs: ## (or reqs) compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs




# DEVELOPMENT ########

# NOTE: add '127.0.0.1 registry' to /etc/host (needs sudo)
EXTRA_REGISTRY:=registry:5000

.env:
	cp .env-devel $@


.PHONY: up-extra down down-extra run-devel

up-extra: .env down # starts pg stack fixture
	# resolving $@ under environ $<
	docker-compose -f docker-compose-extra.yml config
	# starting database stack as defined in  ...
	docker-compose -f docker-compose-extra.yml up --detach


down down-extra:  ## stops extra stack
	# stopping extra services
	-@docker-compose -f docker-compose-extra.yml down

run-devel: .env up-extra  ## starts app with extra stack
	# start app (within $<) in devel mode
	uvicorn $(APP_PACKAGE_NAME).__main__:the_app \
		--reload --reload-dir $(SRC_DIR) \
		--port=8000 --host=0.0.0.0

run-prod: .env up-extra
	# start app (within $<) in prod mode
	$(APP_CLI_NAME)


.PHONY: transfer-images-to-registry
transfer-images-to-registry: ## transfer images to registry
	# pushing sleeper image
	@docker pull itisfoundation/sleeper:1.0.0
	@docker tag itisfoundation/sleeper:1.0.0 $(EXTRA_REGISTRY)/simcore/services/comp/itis/sleeper:1.0.0
	@docker push $(EXTRA_REGISTRY)/simcore/services/comp/itis/sleeper:1.0.0
	# completed transfer of images
	curl -s $(EXTRA_REGISTRY)/v2/_catalog | jq '.repositories'
	curl -s $(EXTRA_REGISTRY)/v2/simcore/services/comp/itis/sleeper/tags/list?n=50 | jq '.'



# BUILD #####################

.PHONY: build build-nc build-devel build-devel-nc build-cache build-cache-nc
build build-nc build-devel build-devel-nc build-cache build-cache-nc: ## docker image build in many flavours
	# building ${APP_NAME} ...
	@$(MAKE_C) ${REPO_BASE_DIR} $@ target=${APP_NAME}


.PHONY: openapi-specs openapi.json
openapi-specs: openapi.json
openapi.json:
	# generating openapi specs file
	python3 -c "import json; from $(APP_PACKAGE_NAME).__main__ import *; print( json.dumps(the_app.openapi(), indent=2) )" > $@

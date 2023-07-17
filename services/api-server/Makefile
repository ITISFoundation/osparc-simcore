#
# Targets for DEVELOPMENT of Public API Server
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

.PHONY: reqs
reqs: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs



.env:
	cp .env-devel $@


# specification of the used openapi-generator-cli (see also https://github.com/ITISFoundation/openapi-generator)
OPENAPI_GENERATOR_NAME := itisfoundation/openapi-generator-cli-openapi-generator-v4.2.3
OPENAPI_GENERATOR_TAG := v0
OPENAPI_GENERATOR_IMAGE := $(OPENAPI_GENERATOR_NAME):$(OPENAPI_GENERATOR_TAG)

define _create_and_validate_openapi
	# generating openapi specs file under $< (NOTE: Skips DEV FEATURES since this OAS is the 'offically released'!)
	@source .env; \
	export API_SERVER_DEV_FEATURES_ENABLED=$1; \
	python3 -c "import json; from $(APP_PACKAGE_NAME).main import *; print( json.dumps(the_app.openapi(), indent=2) )" > $@

	# validates OAS file: $@
	docker run --rm \
			--volume "$(CURDIR):/local" \
			$(OPENAPI_GENERATOR_IMAGE) validate --input-spec /local/$@

endef


.PHONY: openapi-specs openapi.json openapi-dev.json

openapi-specs: openapi.json

openapi.json: .env ## Creates OAS (API_SERVER_DEV_FEATURES_ENABLED=0)
	@$(call _create_and_validate_openapi,0)

openapi-dev.json: .env ## Creates OAS under development (API_SERVER_DEV_FEATURES_ENABLED=1)
	@$(call _create_and_validate_openapi,1)


CLIENT_RELEASE=0.5.0
CLIENT_OAS_PATH=osparc-simcore-clients-$(CLIENT_RELEASE)/api/openapi.json

openapi-client.json:
	# download artifacts for $(CLIENT_RELEASE)
	@temp_dir=$$(mktemp --directory); \
	cd "$$temp_dir"; \
	wget --output-document=artifacts.zip "https://github.com/ITISFoundation/osparc-simcore-clients/archive/refs/tags/v$(CLIENT_RELEASE).zip"; \
	unzip artifacts.zip "$(CLIENT_OAS_PATH)";\
	mv "$(CLIENT_OAS_PATH)" "$(CURDIR)/$@";\
	rm -rf "$$temp_dir"


define _openapi_diff_inputs
	$(SCRIPTS_DIR)/openapi-diff.bash $(foreach f,$^,/specs/$f) --fail-on-incompatible --json=/specs/$@
endef

.PHONY: openapi-diff-dev.json
openapi-dev-diff.json: openapi.json openapi-dev.json ## Diffs against newer openapi-dev.json and checks backwards compatibility
	$(call _openapi_diff_inputs)

openapi-client-diff.json: openapi-client.json openapi.json ## Diffs against older openapi-client.json and checks backwards compatibility
	$(call _openapi_diff_inputs)


# SEE https://schemathesis.readthedocs.io/en/stable/index.html
APP_URL:=http://$(get_my_ip).nip.io:8006

test-api: ## Runs schemathesis against development server (NOTE: make up-devel first)
	@docker run schemathesis/schemathesis:stable run \
		"$(APP_URL)/api/v0/openapi.json"

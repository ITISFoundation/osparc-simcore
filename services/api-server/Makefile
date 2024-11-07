#
# Targets for DEVELOPMENT of Public API Server
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

# Check that given variables are set and all have non-empty values,
# die with an error otherwise.
#
# Params:
#   1. Variable name(s) to test.
#   2. (optional) Error message to print.
guard-%:
	@ if [ "${${*}}" = "" ]; then \
		echo "Environment variable $* not set"; \
		exit 1; \
	fi

.PHONY: reqs
reqs: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs



.env:
	cp .env-devel $@


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


openapi-client-master.json:
	wget -O $@ https://raw.githubusercontent.com/ITISFoundation/osparc-simcore-clients/master/api/openapi.json


define _openapi_diff_inputs
	$(SCRIPTS_DIR)/openapi-diff.bash diff $(foreach f,$^,/specs/$f) --format json > $@
	$(SCRIPTS_DIR)/openapi-diff.bash breaking $(foreach f,$^,/specs/$f) --fail-on ERR > /dev/null
endef

# Examples:
#  make openapi-dev-diff.json
#  make openapi-client-master-diff.json
#  make openapi-client-diff.json
openapi-%-diff.json: openapi.json openapi-%.json ## Diffs against newer or older openapi-%.json and checks backwards compatibility
	$(call _openapi_diff_inputs)

openapi-diff.md: guard-OPENAPI_JSON_BASE_URL openapi.json ## Diffs against a remote openapi.json. E.g. OPENAPI_JSON_BASE_URL=https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/refs/heads/master/services/api-server/openapi.json
	$(SCRIPTS_DIR)/openapi-diff.bash diff $(OPENAPI_JSON_BASE_URL) /specs/openapi.json --format markup --flatten-allof --exclude-elements title,description > $@
	$(SCRIPTS_DIR)/openapi-diff.bash breaking $(OPENAPI_JSON_BASE_URL) /specs/openapi.json --flatten-allof --fail-on ERR

# SEE https://schemathesis.readthedocs.io/en/stable/index.html
APP_URL:=http://$(get_my_ip).nip.io:8006

test-api: ## Runs schemathesis against development server (NOTE: make up-devel first)
	@docker run schemathesis/schemathesis:stable run \
		"$(APP_URL)/api/v0/openapi.json"

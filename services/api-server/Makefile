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

openapi-diff.json: openapi.json openapi-dev.json ## Diffs openapi.json and openapi-dev.json and checks backwards compatibility
	$(SCRIPTS_DIR)/openapi-diff.bash $(foreach f,$^,/specs/$f) --fail-on-incompatible --json=/specs/$@



# SEE https://schemathesis.readthedocs.io/en/stable/index.html
APP_URL:=http://$(get_my_ip).nip.io:8006

test-api: ## Runs schemathesis against development server (NOTE: make up-devel first)
	@docker run schemathesis/schemathesis:stable run \
		"$(APP_URL)/api/v0/openapi.json"


# GENERATION python client ###########################################################################
.PHONY: python-client generator-help python-client-openapi-branch

# SEE https://openapi-generator.tech/docs/usage#generate
# SEE https://openapi-generator.tech/docs/generators/python
#
# TODO: put instead to additional-props.yaml and --config=openapi-generator/python-config.yaml
# TODO: copy this code to https://github.com/ITISFoundation/osparc-simcore-clients/blob/master/Makefile
#
# NOTE: assumes this repo exists
GIT_USER_ID := ITISFoundation
GIT_CLIENT_REPO_ID := osparc-simcore-clients
GIT_OPENAPI_REPO_ID := openapi-generator
GENERATOR_NAME := python
ADDITIONAL_PROPS := \
	generateSourceCodeOnly=false\
	hideGenerationTimestamp=true\
	library=urllib3\
	packageName=osparc\
	packageUrl=https://github.com/$(GIT_USER_ID)/${GIT_CLIENT_REPO_ID}.git\
	packageVersion=$(APP_VERSION)\
	projectName=osparc-simcore-python-api
ADDITIONAL_PROPS := $(foreach prop,$(ADDITIONAL_PROPS),$(strip $(prop)))

null  :=
space := $(null) #
comma := ,

client:
	# cloning $(GIT_USER_ID)/$(GIT_CLIENT_REPO_ID) -> $@
	git clone git@github.com:$(GIT_USER_ID)/$(GIT_CLIENT_REPO_ID).git $@
	# TODO: if fails, add -b
	cd client; git checkout -b "upgrade-${APP_VERSION}"

python-client: client openapi.json ## runs python client generator
	# copies latest version of the openapi
	@cp openapi.json client/api/
	# generates
	@source .env; \
	docker run --rm \
			--volume "$(CURDIR):/local" \
			$(OPENAPI_GENERATOR_IMAGE) generate \
			--generator-name=$(GENERATOR_NAME) \
			--git-user-id=$(GIT_USER_ID) \
			--git-repo-id=$(GIT_CLIENT_REPO_ID) \
			--http-user-agent="osparc-api/$(APP_VERSION)/python" \
			--input-spec=/local/openapi.json \
			--output=/local/client \
			--additional-properties=$(subst $(space),$(comma),$(strip $(ADDITIONAL_PROPS))) \
			--package-name=osparc \
			--release-note="Updated to $(APP_VERSION)"

generator-help: ## help on client-api generator
	# generate help
	@docker run --rm $(OPENAPI_GENERATOR_IMAGE) help generate

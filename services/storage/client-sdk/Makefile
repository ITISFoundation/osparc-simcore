# AUTO-GENERATION of python client SDK
#
#
# SEE https://openapi-generator.tech/docs/usage#generate
# SEE https://openapi-generator.tech/docs/generators/python
#

#
# WARNING: DO NOT USE until codegen.sh is deprecated!
# TODO: Current generator will NOT produce the same client-sdk code since
# bundling openapi.yaml did not preserve e.g. the same schema models !!
#

.DEFAULT_GOAL := generator-help


PACKAGE_NAME := simcore_service_storage_sdk

GIT_USER_ID := ITISFoundation
GIT_REPO_ID := osparc-simcore

GENERATOR_NAME := python

REPO_BASE_DIR := $(shell git rev-parse --show-toplevel)
SCRIPTS_DIR   := $(abspath $(REPO_BASE_DIR)/scripts)
OAS_PATH      := $(abspath $(CURDIR)/../src/simcore_service_storage/api/v0/openapi.yaml)
REL_CURDIR    := $(subst $(REPO_BASE_DIR)/,,$(CURDIR))
FRAGMENT      := \#egg=$(PACKAGE_NAME)&subdirectory=$(REL_CURDIR)

ADDITIONAL_PROPS := \
	generateSourceCodeOnly=false\
	hideGenerationTimestamp=true\
	library=asyncio\
	packageName=$(PACKAGE_NAME)\
	packageUrl="https://github.com/$(GIT_USER_ID)/${GIT_REPO_ID}.git$(FRAGMENT)"\
	packageVersion=$(APP_VERSION)\
	projectName=simcore-service-storage-sdk\
	projectDescription="Data storage manager service client's SDK"\

ADDITIONAL_PROPS := $(foreach prop,$(ADDITIONAL_PROPS),$(strip $(prop)))

null  :=
space := $(null) #
comma := ,


.PHONY: python-client generator-help

openapi.yaml: $(OAS_PATH)
	cp $< $@

python-client: openapi.yaml ## runs python client generator
	cd $(CURDIR); \
	$(SCRIPTS_DIR)/openapi-generator-cli.bash generate \
		--generator-name=$(GENERATOR_NAME) \
		--git-user-id=$(GIT_USER_ID)\
		--git-repo-id=$(GIT_REPO_ID)\
		--http-user-agent="$(PACKAGE_NAME)/{packageVersion}/{language}"\
		--input-spec=/local/$< \
		--output=/local/$@ \
		--additional-properties=$(subst $(space),$(comma),$(strip $(ADDITIONAL_PROPS)))\
		--package-name=$(PACKAGE_NAME)\
		--release-note="Updated to $(APP_VERSION)"
	# deleting $<
	-@rm $<


generator-help: ## help on client-api generator
	# generate help
	@$(SCRIPTS_DIR)/openapi-generator-cli.bash help generate
	# generator config help
	@$(SCRIPTS_DIR)/openapi-generator-cli.bash config-help -g $(GENERATOR_NAME)

#
# Targets for DEVELOPMENT of models Library
#
include ../../scripts/common.Makefile
include ../../scripts/common-package.Makefile

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


.PHONY: tests
tests: ## runs unit tests
	# running unit tests
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests



# INTEGRATION -----------------------------------
METADATA = metadata/metadata.yml

service.cli/run: $(METADATA)
	# Updates adapter script from metadata in $<
	@python3 simcore-service-integration run_creator --metadata $< --runscript $@

docker-compose-meta.yml: $(METADATA)
	# Injects metadata from $< as labels
	@python3 simcore-service-integration update_compose_labels --compose $@ --metadata $<

define _docker_compose_build
export DOCKER_BUILD_TARGET=$(if $(findstring -devel,$@),development,$(if $(findstring -cache,$@),cache,production)); \
$(if $(findstring -x,$@),\
	docker buildx > /dev/null; export DOCKER_CLI_EXPERIMENTAL=enabled; docker buildx bake  --file docker-compose-build.yml --file docker-compose-meta.yml $(if $(findstring -nc,$@),--no-cache,);,\
	$(if $(findstring -kit,$@),export DOCKER_BUILDKIT=1;export COMPOSE_DOCKER_CLI_BUILD=1;,) \
	docker-compose --file docker-compose-build.yml --file docker-compose-meta.yml build $(if $(findstring -nc,$@),--no-cache,) --parallel;\
)
endef




# PUBLISHING -----------------------------------
#
# 1. versioning of the service should be decided by the author. The only constraint is to determine an order between the different releases and determine e.g. whether there is a patch etc
# 2. every new version should come with a CHANGELOG showing changes and follows https://keepachangelog.com/en/1.0.0/. It is important that we can see changes!?
# 3. integration version is more strict and follows semantic version. service should NOT change this but just point to the right one. Available versions should be published by the framework.
#
#
#  a) because of (1), we need to change the schemas for service version.
#  b) we can ship a version-semantics release approach that simplifies above.
#
#
define _bumpversion
	# upgrades as $(subst $(1),,$@) version, commits and tags
	@bump2version --verbose --list --config-file $(1) $(subst $(2),,$@)
endef

.PHONY: version-service-patch version-service-minor version-service-major
version-service-patch version-service-minor version-service-major: versioning/service.cfg ## kernel/service versioning as patch
	@$(call _bumpversion,$<,version-service-)

.PHONY: push push-force push-version push-latest pull-latest pull-version tag-latest tag-version
tag-latest tag-version:
	docker tag local/$(DOCKER_IMAGE_NAME):production $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(if $(findstring version,$@),$(DOCKER_IMAGE_TAG),latest)

version_valid = $(shell test $$(echo $(DOCKER_IMAGE_TAG) | cut --fields=1 --delimiter=.) -gt 0 > /dev/null && echo "image version is valid")
version_exists = $(shell DOCKER_CLI_EXPERIMENTAL=enabled docker manifest inspect $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) > /dev/null && echo "image already exists on $(DOCKER_REGISTRY)")
push push-force: ## pushes (resp. force) services to the registry if service not available in registry.
	@$(if $(findstring force,$@),,\
		$(if $(call version_valid),$(info version is valid), $(error $(DOCKER_IMAGE_TAG) is not a valid version (major>=1)))\
		$(if $(call version_exists),$(error $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) already exists on $(DOCKER_REGISTRY)), $(info no version found on $(DOCKER_REGISTRY)))\
	)
	@$(MAKE) push-version;
	@$(MAKE) push-latest;

push-latest push-version: ## publish service to registry with latest/version tag
	# pushing '$(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(if $(findstring version,$@),$(DOCKER_IMAGE_TAG),latest)'...
	@$(MAKE) tag-$(subst push-,,$@)
	@docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(if $(findstring version,$@),$(DOCKER_IMAGE_TAG),latest)
	# pushed '$(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(if $(findstring version,$@),$(DOCKER_IMAGE_TAG),latest)'

pull-latest pull-version: ## pull service from registry
	@docker pull $(DOCKER_REGISTRY)/$(DOCKER_IMAGE_NAME):$(if $(findstring version,$@),$(DOCKER_IMAGE_TAG),latest)


.PHONY: version-integration-patch version-integration-minor version-integration-major
version-integration-patch version-integration-minor version-integration-major: versioning/integration.cfg ## integration versioning as patch (bug fixes not affecting API/handling), minor/major (backwards-compatible/INcompatible API changes)
	@$(call _bumpversion,$<,version-integration-)

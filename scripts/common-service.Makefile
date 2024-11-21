#
# These are common target and recipes to Makefiles for services/
#
# USAGE: Add this in the top of service's Makefile
#
#   include ../../scripts/common.Makefile
#   include ../../scripts/common-service.Makefile
#

#
# GLOBALS
#

# NOTE $(CURDIR) in this file refers to the directory where this file is included

# Variable based on conventions (override if they do not apply)
APP_NAME          = $(notdir $(CURDIR))
APP_CLI_NAME      = simcore-service-$(APP_NAME)
APP_PACKAGE_NAME  = $(subst -,_,$(APP_CLI_NAME))
APP_VERSION      := $(shell cat VERSION)
SRC_DIR           = $(abspath $(CURDIR)/src/$(APP_PACKAGE_NAME))

export APP_VERSION


#
# SHORTCUTS
#


#
# VENV (virtual environment) TASKS
#


.PHONY: install-dev install-prod install-ci

install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# Installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt



.PHONY: test-dev-unit test-ci-unit test-dev-integration test-ci-integration test-dev

TEST_PATH := $(if $(test-path),/$(patsubst tests/integration/%,%, $(patsubst tests/unit/%,%, $(patsubst %/,%,$(test-path)))),)
test-dev-unit test-ci-unit: _check_venv_active ## run app unit tests (specifying test-path can restrict to a folder)
	# Targets tests/unit folder
	@make --no-print-directory _run-$(subst -unit,,$@) target=$(CURDIR)/tests/unit$(TEST_PATH)

test-dev-integration test-ci-integration: ## run app integration tests (specifying test-path can restrict to a folder)
	# Targets tests/integration folder using local/$(image-name):production images
	@export DOCKER_REGISTRY=local; \
	export DOCKER_IMAGE_TAG=production; \
	make --no-print-directory _run-$(subst -integration,,$@) target=$(CURDIR)/tests/integration$(TEST_PATH)


test-dev: test-dev-unit test-dev-integration ## runs unit and integration tests for development (e.g. w/ pdb)

test-ci: test-ci-unit test-ci-integration ## runs unit and integration tests for CI


#
# DOCKER CONTAINERS TASKS
#

.PHONY: build build-nc build-devel build-devel-nc
build build-nc build-devel build-devel-nc: ## [docker] builds docker image in many flavours
	# Building docker image for ${APP_NAME} ...
	@$(MAKE_C) ${REPO_BASE_DIR} $@ target=${APP_NAME}


.PHONY: shell
shell: ## [swarm] runs shell inside $(APP_NAME) container
	docker exec \
		--interactive \
		--tty \
		$(shell docker ps -f "name=simcore_$(APP_NAME)*" --format {{.ID}}) \
		/bin/bash


.PHONY: tail logs
tail logs: ## [swarm] tails log of $(APP_NAME) container
	docker logs \
		--follow \
		$(shell docker ps --filter "name=simcore_$(APP_NAME)*" --format {{.ID}}) \
		2>&1


.PHONY: stats
stats: ## [swarm] display live stream of $(APP_NAME) container resource usage statistics
	docker stats $(shell docker ps -f "name=simcore_$(APP_NAME)*" --format {{.ID}})



DOCKER_REGISTRY ?=local
DOCKER_IMAGE_TAG?=production

.PHONY: settings-schema.json
settings-schema.json: ## [container] dumps json-shcema of this service settings
	# Dumping settings schema of ${DOCKER_REGISTRY}/${APP_NAME}:${DOCKER_IMAGE_TAG}
	@docker run \
		${DOCKER_REGISTRY}/${APP_NAME}:${DOCKER_IMAGE_TAG} \
		${APP_CLI_NAME} settings --as-json-schema \
		| sed --expression='1,/{/ {/{/!d}' \
		> $@
	# Dumped '$(CURDIR)/$@'

# NOTE: settings CLI prints some logs in the header from the boot and entrypoint scripts. We
# use strema editor expression (sed --expression) to trim them:
# - 1,/{/: This specifies the range of lines to operate on, in this case, from the first line to (but not including) the line that contains the string "{".
# - {/{/!d}: This specifies that all lines between the first line and the line that contains "{" should be printed ({) except for the line that contains "{" (/{/!d).
#



#
# MISC
#

.PHONY: info
info: ## displays service info
	@make --no-print-directory info-super
	# service setup
	@echo ' APP_NAME         : $(APP_NAME)'
	@echo ' APP_CLI_NAME     : ${APP_CLI_NAME}'
	@echo ' APP_PACKAGE_NAME : ${APP_PACKAGE_NAME}'
	@echo ' APP_VERSION      : ${APP_VERSION}'
	@echo ' SRC_DIR          : ${SRC_DIR}'



#
# SUBTASKS
#

.PHONY: _run-test-dev _run-test-ci

TEST_TARGET := $(if $(target),$(target),$(CURDIR)/tests/unit)
PYTEST_ADDITIONAL_PARAMETERS := $(if $(pytest-parameters),$(pytest-parameters),)
_run-test-dev: _check_venv_active
	# runs tests for development (e.g w/ pdb)
	pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--junitxml=junit.xml -o junit_family=legacy \
		--cov=$(APP_PACKAGE_NAME) \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--keep-docker-up \
		--pdb \
		-vv \
		$(PYTEST_ADDITIONAL_PARAMETERS) \
		$(TEST_TARGET)


_run-test-ci: _check_venv_active
	# runs tests for CI (e.g. w/o pdb but w/ converage)
	pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-append \
		--cov-config=.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--junitxml=junit.xml -o junit_family=legacy \
		--cov=$(APP_PACKAGE_NAME) \
		--durations=10 \
		--keep-docker-up \
		--log-date-format="%Y-%m-%d %H:%M:%S" \
    --log-format="%(asctime)s %(levelname)s %(message)s" \
		--verbose \
		-m "not heavy_load" \
		$(PYTEST_ADDITIONAL_PARAMETERS) \
		$(TEST_TARGET)


.PHONY: _assert_target_defined
_assert_target_defined:
	$(if $(target),,$(error unset argument 'target' is required))




#
# OPENAPI SPECIFICATIONS ROUTINES
#


# specification of the used openapi-generator-cli (see also https://github.com/ITISFoundation/openapi-generator)
OPENAPI_GENERATOR_NAME := openapitools/openapi-generator-cli
OPENAPI_GENERATOR_TAG := latest
OPENAPI_GENERATOR_IMAGE := $(OPENAPI_GENERATOR_NAME):$(OPENAPI_GENERATOR_TAG)

define validate_openapi_specs
	# Validating OAS '$(1)' ...
	docker run --rm \
			--volume "$(CURDIR):/local" \
			$(OPENAPI_GENERATOR_IMAGE) validate --input-spec /local/$(strip $(1))
endef

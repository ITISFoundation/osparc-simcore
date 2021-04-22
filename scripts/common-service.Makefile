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
# COMMON TASKS
#

.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "INFO $@ does not exist, cloning $< as $@"; cp $< $@)


.PHONY: install-dev install-prod install-ci

install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# Installing in $(subst install-,,$@) mode
	pip-sync --pip-args="--use-feature=in-tree-build" requirements/$(subst install-,,$@).txt

## 2021.06.03
## DEPRECATION: A future pip version will change local packages to be built in-place without first copying to a temporary directory.
## We recommend you use --use-feature=in-tree-build to test your packages with this new behavior before it becomes the default.
## pip 21.3 will remove support for this functionality. You can find discussion regarding this at https://github.com/pypa/pip/issues/7555.


.PHONY: test-dev-unit test-ci-unit test-dev-integration test-ci-integration test-dev

test-dev-unit test-ci-unit: _check_venv_active
	# Targets tests/unit folder
	@make --no-print-directory _run-$(subst -unit,,$@) target=$(CURDIR)/tests/unit

test-dev-integration test-ci-integration:
	# Targets tests/integration folder using local/$(image-name):production images
	@export DOCKER_REGISTRY=local; \
	export DOCKER_IMAGE_TAG=production; \
	make --no-print-directory _run-$(subst -integration,,$@) target=$(CURDIR)/tests/integration


test-dev: test-dev-unit test-dev-integration ## runs unit and integration tests for development (e.g. w/ pdb)

test-ci: test-ci-unit test-ci-integration ## runs unit and integration tests for CI


.PHONY: build build-nc build-devel build-devel-nc
build build-nc build-devel build-devel-nc: ## builds docker image in many flavours
	# Building docker image for ${APP_NAME} ...
	@$(MAKE_C) ${REPO_BASE_DIR} $@ target=${APP_NAME}


.PHONY: shell
shell: ## runs shell inside $(APP_NAME) container
	docker exec -it $(shell docker ps -f "name=$(APP_NAME)*" --format {{.ID}}) /bin/bash


.PHONY: tail
tail: ## tails log of $(APP_NAME) container
	docker logs --follow $(shell docker ps --filter "name=$(APP_NAME)*" --format {{.ID}}) 2>&1


.PHONY: stats
stats: ## display live stream of $(APP_NAME) container resource usage statistics
	docker stats $(shell docker ps -f "name=$(APP_NAME)*" --format {{.ID}})


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

_run-test-dev: _check_venv_active
	# runs tests for development (e.g w/ pdb)
	pytest -vv --exitfirst --failed-first --durations=10 --pdb --color=yes --cov=$(APP_PACKAGE_NAME) --cov-report=term-missing --cov-config=.coveragerc $(TEST_TARGET)


_run-test-ci: _check_venv_active
	# runs tests for CI (e.g. w/o pdb but w/ converage)
	pytest --cov=$(APP_PACKAGE_NAME) --durations=10 --cov-append --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc -v -m "not travis" $(TEST_TARGET)


.PHONY: _assert_target_defined
_assert_target_defined:
	$(if $(target),,$(error unset argument 'target' is required))

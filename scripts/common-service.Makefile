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

.PHONY: build build-nc build-devel build-devel-nc build-cache build-cache-nc
build build-nc build-devel build-devel-nc build-cache build-cache-nc: ## builds docker image in many flavours
	# building docker image for ${APP_NAME} ...
	@$(MAKE_C) ${REPO_BASE_DIR} $@ target=${APP_NAME}


.PHONY: shell
shell: ## runs shell in production container
	# runs ${APP_NAME}:production shell
	docker run -it --name="${APP_NAME}_${APP_VERSION}_shell" local/${APP_NAME}:production /bin/bash


.PHONY: tail
tail: ## tails log of $(APP_NAME) container
	docker logs --follow $(shell docker ps -f "name=$(APP_NAME)*" --format {{.ID}}) > $(APP_NAME).log 2>&1


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

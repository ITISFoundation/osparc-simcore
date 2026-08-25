#
# DEVELOPMENT recipes for migration
#


.DEFAULT_GOAL := help

include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/service.mk

.PHONY: requirements reqs
requirements reqs: ## (or reqs) compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs

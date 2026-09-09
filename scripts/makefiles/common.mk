#
# COMMON targets and recipes for **packages/ and services/**.
#
# LIBRARY (.mk): include-only, not a directly-invoked entry point.
# This is the aggregator included at the top of every package/service Makefile
# (packages then add package.mk, services add service.mk).
# $(CURDIR) here refers to the directory of the top-level Makefile that includes it.
# SEE scripts/makefiles/README.md for conventions.
#

_MK_DIR := $(dir $(lastword $(MAKEFILE_LIST)))
include $(_MK_DIR)globals.mk
include $(REPO_BASE_DIR)/scripts/makefiles/help.mk
include $(REPO_BASE_DIR)/scripts/makefiles/python-lint.mk
include $(REPO_BASE_DIR)/scripts/makefiles/version.mk


#
# COMMON TASKS (alphabetically ordered)
#

##@ Environment & Install

.PHONY: clean
_GIT_CLEAN_ARGS = -dxf -e .vscode
clean: ## Cleans all unversioned files in project and temp files create by this makefile
	# Cleaning unversioned
	@git clean -n $(_GIT_CLEAN_ARGS)
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo -n "$(shell whoami), are you REALLY sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@git clean $(_GIT_CLEAN_ARGS)


.env: .env-devel ## Creates .env file from defaults in .env-devel
	$(clone_from_template)


.PHONY: devenv
devenv: ## Build development environment
	@$(MAKE_C) $(REPO_BASE_DIR) $@


##@ Misc

.PHONY: github-workflow-job
github-workflow-job: ## Runs a github workflow job using act locally, run using "make github-workflow-job job=JOB_NAME"
	# running job "${job}"
	$(SCRIPTS_DIR)/act.bash ../.. ${job}


.PHONY: info
inf%: ## Displays basic info
	# system
	@echo ' OS               : $(IS_LINUX)$(IS_OSX)$(IS_WSL)$(IS_WIN)'
	@echo ' CURDIR           : ${CURDIR}'
	@echo ' NOW_TIMESTAMP    : ${NOW_TIMESTAMP}'
	@echo ' VCS_URL          : ${VCS_URL}'
	@echo ' VCS_REF          : ${VCS_REF}'
	# installed in .venv
	@uv pip list
	# package setup
	-@echo ' name         : ' $(shell python ${CURDIR}/setup.py --name)
	-@echo ' version      : ' $(shell python ${CURDIR}/setup.py --version)
	-@echo ' authors      : ' "$(shell python ${CURDIR}/setup.py --author)"
	-@echo ' description  : ' "$(shell python ${CURDIR}/setup.py --description)"


# REVIEW: diagnostics-only, no known CI/docs callers (was tagged `.PHONE`, i.e. never phony).
.PHONY: pip-freeze
pip-freeze: ## Dumps current environ and base.txt [diagnostics]
	pip freeze > freeze-now.ignore.txt
	cat requirements/_base.txt | grep -v '#' > freeze-base.ignore.txt

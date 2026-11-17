#
# Targets for DEVELOPMENT of the CodSpeed benchmark suite
#
.DEFAULT_GOAL := help

include ../../scripts/makefiles/common.mk


.PHONY: requirements reqs
requirements reqs: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install install-dev install-ci
install: install-dev

install-dev install-ci: ## install requirements in dev/ci mode
	# installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt


.PHONY: benchmarks benchmarks-ci
benchmarks: ## runs the benchmarks locally (walltime, no instrumentation)
	@$(VENV_DIR)/bin/pytest --codspeed -vv $(CURDIR)

# CI-CONTRACT: benchmarks-ci is invoked by ci/github/benchmarks/codspeed.bash
benchmarks-ci: ## runs the benchmarks under the CodSpeed instrumentation [CI]
	@$(VENV_DIR)/bin/pytest --codspeed --color=yes -v -p no:cacheprovider $(CURDIR)

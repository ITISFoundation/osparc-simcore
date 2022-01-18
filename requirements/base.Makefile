# Base Makefile for all requirements/Makefile
#
# SEE docs/python-dependencies.md
#
REPO_BASE_DIR := $(shell git rev-parse --show-toplevel)


.PHONY: touch reqs check clean help
.DEFAULT_GOAL := help

DO_CLEAN_OR_UPGRADE:=$(if $(clean),,--upgrade)
UPGRADE_OPTION := $(if $(upgrade),--upgrade-package $(upgrade),$(DO_CLEAN_OR_UPGRADE))


objects = $(sort $(wildcard *.in))
outputs := $(objects:.in=.txt)

reqs: $(outputs) ## pip-compiles all requirements/*.in -> requirements/*.txt; make reqs upgrade=foo will only upgrade package foo

touch:
	@$(foreach p,${objects},touch ${p};)


check: ## Checks whether pip-compile is installed
	@which pip-compile > /dev/null


clean: check ## Cleans all requirements/*.txt
	- rm $(outputs)


.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""


# ------------------------------------------------------------------------------------------
# NOTE: runs above requirememts/ such that comments sync with dependabot's
# NOTE: adds --strip-extras since compiled reqs (*.txt) freezes the dependencies. This also simplifies
#       extracting subsets of requiremenst like e.g _dask-distributed.* and _dask-complete.*
#
%.txt: %.in
	cd ..; \
	pip-compile $(UPGRADE_OPTION) --build-isolation --strip-extras --output-file requirements/$@ requirements/$<

_test.txt: _base.txt

_tools.txt: _tools.in _base.txt _test.txt $(REPO_BASE_DIR)/requirements/devenv.txt

# ------------------------------------------------------------------------------------------

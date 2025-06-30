# Base Makefile for all requirements/Makefile
#
# SEE docs/python-dependencies.md
#
REPO_BASE_DIR := $(shell git rev-parse --show-toplevel)


.PHONY: touch reqs check clean help
.DEFAULT_GOAL := help

DO_CLEAN_OR_UPGRADE:=$(if $(clean),,--upgrade)
STARTSWITH_UPGRADE := $(if $(startswith),$(shell grep '^$(startswith)' $(basename $@).txt 2>/dev/null | cut -d= -f1 | xargs -n1 echo --upgrade-package),)
UPGRADE_OPTION := $(if $(upgrade),--upgrade-package "$(upgrade)",$(if $(startswith),$(STARTSWITH_UPGRADE),$(DO_CLEAN_OR_UPGRADE))


objects = $(sort $(wildcard *.in))
outputs := $(objects:.in=.txt)

reqs: $(outputs) ## pip-compiles all requirements/*.in -> requirements/*.txt; make reqs upgrade=foo will only upgrade package foo; make reqs startswith=pytest will upgrade packages starting with pytest

touch:
	@$(foreach p,${objects},touch ${p};)


check: ## Checks whether uv is installed
	@which uv > /dev/null


clean: check ## Cleans all requirements/*.txt
	- rm $(outputs)


.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Examples:"
	@echo "  make reqs                   # Upgrade all packages"
	@echo "  make reqs upgrade=pytest    # Upgrade only pytest package"
	@echo "  make reqs startswith=pytest # Upgrade all packages starting with 'pytest'"
	@echo "  make reqs clean=1           # Clean and rebuild all requirements"
	@echo ""


# ------------------------------------------------------------------------------------------
# NOTE: runs above requirememts/ such that comments sync with dependabot's
# NOTE: adds --strip-extras since compiled reqs (*.txt) freezes the dependencies. This also simplifies
#       extracting subsets of requiremenst like e.g _dask-distributed.*
#
%.txt: %.in
	cd ..; \
	uv pip compile $(UPGRADE_OPTION) \
		--no-header \
		--output-file requirements/$@ requirements/$<

_test.txt: _base.txt

_tools.txt: _tools.in _base.txt _test.txt $(REPO_BASE_DIR)/requirements/devenv.txt

# ------------------------------------------------------------------------------------------

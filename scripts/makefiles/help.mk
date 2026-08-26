#
# Shared help target for Makefiles in this repository.
#
# USAGE: include this file in any Makefile (no REPO_BASE_DIR dependency —
# it locates its own help.awk). Requires GNU awk for sorting.
# Add '## description' after a target to make it appear in the output.
# Add a '##@ Section Name' comment above a group of targets to label it; the
# same section name reused across included files merges into one group.
# SEE scripts/makefiles/README.md for the full convention.
#
# Example:
#   include $(REPO_BASE_DIR)/scripts/makefiles/help.mk
#

_HELP_MK_DIR := $(dir $(lastword $(MAKEFILE_LIST)))

.PHONY: _help help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
_help:
	@echo "usage: make [target] ..."
	@echo ""
	@echo "Targets for '$(notdir $(CURDIR))':"
	@echo ""
	@gawk -f $(_HELP_MK_DIR)help.awk $(MAKEFILE_LIST)
	@echo ""

help: _help

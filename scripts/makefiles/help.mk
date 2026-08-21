#
# Shared help target for Makefiles in this repository.
#
# USAGE: include this file in any Makefile (no REPO_BASE_DIR dependency —
# it locates its own help.awk).
# Add '## description' after a target to make it appear in the output.
# Add a '##@ Section Name' comment above a group of targets to label it; the
# same section name reused across included files merges into one group.
# SEE scripts/makefiles/README.md for the full convention.
#
# Example:
#   include $(REPO_BASE_DIR)/scripts/makefiles/help.mk
#

_HELP_MK_DIR := $(dir $(lastword $(MAKEFILE_LIST)))

# spellchecker:ignore-next-line
.PHONY: hel%
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
# spellchecker:ignore-next-line
hel%:
	@echo "usage: make [target] ..."
	@echo ""
	@echo "Targets for '$(notdir $(CURDIR))':"
	@echo ""
	@awk -f $(_HELP_MK_DIR)help.awk $(MAKEFILE_LIST)
	@echo ""

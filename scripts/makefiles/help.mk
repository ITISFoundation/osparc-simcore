#
# Shared help target for Makefiles in this repository.
#
# USAGE: include this file in any Makefile (after REPO_BASE_DIR is set).
# Add '## description' after a target to make it appear in the output.
#
# Example:
#   include $(REPO_BASE_DIR)/scripts/makefiles/help.make
#

# spellchecker:ignore-next-line
.PHONY: hel%
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
# spellchecker:ignore-next-line
hel%:
	@echo "usage: make [target] ..."
	@echo ""
	@echo "Targets for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

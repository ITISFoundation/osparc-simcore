#
# Shared i18n targets for services and packages.
#
# USAGE: include this file in common-service.Makefile or common-package.Makefile
# (after REPO_BASE_DIR and SRC_DIR are set by common.Makefile).
#
# Example:
#   include $(REPO_BASE_DIR)/scripts/makefiles/i18n.make
#
# Overridable variables:
#   I18N_SRC_DIR       — source directory to scan (default: $(SRC_DIR))
#   I18N_COMPONENT_NAME — output .pot basename (default: $(notdir $(CURDIR)))
#

I18N_SRC_DIR        ?= $(SRC_DIR)
I18N_COMPONENT_NAME ?= $(notdir $(CURDIR))
I18N_TOOLS          := $(REPO_BASE_DIR)/scripts/i18n/tools
I18N_LOCALE_DIR     := $(REPO_BASE_DIR)/packages/common-library/src/common_library/locale
I18N_PARTIALS       := $(I18N_LOCALE_DIR)/_partials

.PHONY: i18n-extract i18n-translate i18n-compile i18n-check

i18n-extract: ## Extract user_message() strings -> _partials/$(I18N_COMPONENT_NAME).pot
	@mkdir -p $(I18N_PARTIALS)
	@cd $(REPO_BASE_DIR) && \
	uv run $(I18N_TOOLS)/i18n_extractor.py xgettext \
	  --src $$(realpath --relative-to=$(REPO_BASE_DIR) $(I18N_SRC_DIR)) \
	  --out $(I18N_PARTIALS)/$(I18N_COMPONENT_NAME).pot \
	  --langs python

i18n-translate: ## (Delegate) AI translate full catalog via orchestrator
	@$(MAKE_C) $(REPO_BASE_DIR)/scripts/i18n translate

i18n-compile: ## (Delegate) Compile .po -> .mo via orchestrator
	@$(MAKE_C) $(REPO_BASE_DIR)/scripts/i18n compile

i18n-check: ## Validate no f-strings in user_message() calls
	@cd $(REPO_BASE_DIR) && \
	uv run $(I18N_TOOLS)/i18n_extractor.py validate \
	  --src $$(realpath --relative-to=$(REPO_BASE_DIR) $(I18N_SRC_DIR)) \
	  --langs python

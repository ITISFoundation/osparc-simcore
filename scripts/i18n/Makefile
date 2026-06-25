# Orchestrates i18n extraction and translation for the osparc-simcore backend.
# Output catalog: packages/common-library/src/common_library/locale/
#
# Usage (full pipeline):
#   make all
#
# Step-by-step:
#   make extract-all          # gather per-service partial .pots
#   make merge                # msgcat partials -> messages.pot, then enrich with CTX
#   make translate            # AI translate stale entries (one .po per LANG)
#   make compile              # msgfmt .po -> .mo
#
# Frontend (AI translation only; extraction is done by qooxdoo):
#   make frontend-translate
#
# Per-provider shortcuts (translate step only):
#   make translate-ollama
#   make translate-anthropic
#   make translate-openai

REPO_ROOT      := $(shell git rev-parse --show-toplevel)
I18N_TOOLS     := $(REPO_ROOT)/scripts/i18n/tools
LOCALE_OUT_DIR := $(REPO_ROOT)/packages/common-library/src/common_library/locale
PARTIALS_DIR   := $(LOCALE_OUT_DIR)/_partials
ENV_FILE       := $(REPO_ROOT)/.env

# --- Backend configuration ---
LANGS            ?= zh_CN es_ES
POT              := $(LOCALE_OUT_DIR)/messages.pot
PO_FILES         := $(foreach lang,$(LANGS),$(LOCALE_OUT_DIR)/$(lang)/LC_MESSAGES/messages.po)
MO_FILES         := $(PO_FILES:.po=.mo)
MODEL            ?= openai/gpt-4o
BASE_URL         ?=
PARALLEL         ?= false
PROGRESS         ?= true
INCREMENTAL_SAVE ?= true
USE_GIT          ?= true
MAX_WORKERS      ?= 4

# --- Services/packages containing user_message() calls ---
# To rediscover: grep -r 'user_message(' $(REPO_ROOT)/services $(REPO_ROOT)/packages \
#                  --include='*.py' -l | xargs -I{} dirname {} | sort -u
I18N_DIRS := \
  services/web/server \
  services/director-v2 \
  services/api-server \
  services/notifications \
  packages/service-library \
  packages/dask-task-models-library \
  packages/common-library

# --- Frontend configuration ---
CLIENT_DIR         := $(REPO_ROOT)/services/static-webserver/client
CLIENT_TRANS_DIR   := $(CLIENT_DIR)/source/translation
CLIENT_TEMPLATE_PO := $(CLIENT_TRANS_DIR)/en_US.po
CLIENT_LANGS       ?= es_ES zh_CN

# --- Flag helpers ---
ifeq ($(USE_GIT),true)
  USE_GIT_FLAG :=
else
  USE_GIT_FLAG := --no-git
endif

ifeq ($(INCREMENTAL_SAVE),true)
  INCREMENTAL_SAVE_FLAG :=
else
  INCREMENTAL_SAVE_FLAG := --no-incremental-save
endif

ifeq ($(PROGRESS),true)
  PROGRESS_FLAG :=
else
  PROGRESS_FLAG := --no-progress
endif

ifeq ($(PARALLEL),true)
  PARALLEL_FLAG := --parallel
else
  PARALLEL_FLAG := --no-parallel
endif

ifneq ($(BASE_URL),)
  BASE_URL_FLAG := --base-url $(BASE_URL)
else
  BASE_URL_FLAG :=
endif

EXTRACTOR  := uv run $(I18N_TOOLS)/i18n_extractor.py
TRANSLATOR := uv run --env-file $(ENV_FILE) $(I18N_TOOLS)/i18n_translator.py

# ---------------------------------------------------------------------------
.DEFAULT_GOAL := help

.PHONY: all extract-all merge translate compile frontend-translate clean \
        check-i18n-style \
        translate-ollama translate-anthropic translate-openai translate-custom

all: extract-all merge translate compile  ## Full backend pipeline

# ---------------------------------------------------------------------------
# Step 1 — per-service/package partial .pots
# ---------------------------------------------------------------------------
extract-all:  ## Extract user_message() strings from all I18N_DIRS -> _partials/
	@mkdir -p $(PARTIALS_DIR)
	@for dir in $(I18N_DIRS); do \
	  name=$$(basename $$dir); \
	  out=$(PARTIALS_DIR)/$$name.pot; \
	  echo "  [extract] $(REPO_ROOT)/$$dir/src -> $$out"; \
	  cd $(REPO_ROOT) && $(EXTRACTOR) xgettext \
	    --src $$dir/src \
	    --out $$out \
	    --langs python; \
	done

# ---------------------------------------------------------------------------
# Step 2 — merge partials + enrich with CTX snippets
# ---------------------------------------------------------------------------
merge:  ## Merge _partials/*.pot -> messages.pot + enrich with CTX snippets
	@mkdir -p $(LOCALE_OUT_DIR)
	msgcat --use-first $(PARTIALS_DIR)/*.pot -o $(POT)
	$(EXTRACTOR) enrich --pot $(POT) --repo-root $(REPO_ROOT)

# ---------------------------------------------------------------------------
# Step 3 — AI translate stale entries
# ---------------------------------------------------------------------------
translate: $(PO_FILES)  ## AI translate stale entries for all LANGS (runs after merge)

$(LOCALE_OUT_DIR)/%/LC_MESSAGES/messages.po: $(POT)
	@mkdir -p $(@D)
	@if [ -f "$@" ]; then \
	  msgmerge --update --backup=none "$@" "$(POT)"; \
	else \
	  msginit --no-translator --input="$(POT)" --locale="$*" --output-file="$@"; \
	fi
	$(TRANSLATOR) translate \
	  --pot $(POT) \
	  --in-po $@ \
	  --lang $* \
	  --model $(MODEL) \
	  $(BASE_URL_FLAG) \
	  $(USE_GIT_FLAG) \
	  $(INCREMENTAL_SAVE_FLAG) \
	  $(PROGRESS_FLAG) \
	  $(PARALLEL_FLAG) \
	  --max-workers $(MAX_WORKERS) \
	  --log-file $(@D)/translate.log \
	  --out $@

# ---------------------------------------------------------------------------
# Step 4 — compile .po -> .mo
# ---------------------------------------------------------------------------
compile: $(MO_FILES)  ## Compile all .po -> .mo

$(LOCALE_OUT_DIR)/%/LC_MESSAGES/messages.mo: $(LOCALE_OUT_DIR)/%/LC_MESSAGES/messages.po
	msgfmt $< -o $@

# ---------------------------------------------------------------------------
# Frontend — AI translation only (extraction done by qooxdoo via translate-extract)
# ---------------------------------------------------------------------------
frontend-translate:  ## AI translate frontend .po files (CLIENT_LANGS) from en_US.po template
	@for lang in $(CLIENT_LANGS); do \
	  out=$(CLIENT_TRANS_DIR)/$$lang.po; \
	  echo "  [translate] frontend $$lang -> $$out"; \
	  in_po_flag=""; \
	  if [ -f "$$out" ]; then in_po_flag="--in-po $$out"; fi; \
	  uv run --env-file $(ENV_FILE) $(I18N_TOOLS)/i18n_translator.py translate \
	    --pot $(CLIENT_TEMPLATE_PO) \
	    $$in_po_flag \
	    --lang $$lang \
	    --model $(MODEL) \
	    $(BASE_URL_FLAG) \
	    $(USE_GIT_FLAG) \
	    $(INCREMENTAL_SAVE_FLAG) \
	    $(PROGRESS_FLAG) \
	    $(PARALLEL_FLAG) \
	    --max-workers $(MAX_WORKERS) \
	    --log-file $(CLIENT_TRANS_DIR)/translate-$$lang.log \
	    --out $$out; \
	done

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
check-i18n-style:  ## Validate no f-strings in user_message() calls (all I18N_DIRS)
	@for dir in $(I18N_DIRS); do \
	  echo "  [validate] $$dir"; \
	  cd $(REPO_ROOT) && $(EXTRACTOR) validate --src $$dir/src --langs python; \
	done

# ---------------------------------------------------------------------------
# Provider shortcuts (translate step only)
# ---------------------------------------------------------------------------
translate-ollama:     ## Translate with Ollama llama3.1 (local, no API key)
	$(MAKE) translate MODEL=ollama/llama3.1

translate-anthropic:  ## Translate with Anthropic claude-sonnet-4-6
	$(MAKE) translate MODEL=anthropic/claude-sonnet-4-6

translate-openai:     ## Translate with OpenAI gpt-4o
	$(MAKE) translate MODEL=openai/gpt-4o

translate-custom:     ## Translate with custom endpoint (requires MODEL and BASE_URL)
	@test -n "$(MODEL)"    || (echo "MODEL is required"    && false)
	@test -n "$(BASE_URL)" || (echo "BASE_URL is required" && false)
	$(MAKE) translate MODEL=$(MODEL) BASE_URL=$(BASE_URL)

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
clean:  ## Remove _partials/, messages.pot, all .po and .mo files
	rm -rf $(PARTIALS_DIR)
	rm -f $(POT)
	rm -f $(PO_FILES) $(MO_FILES)

# ---------------------------------------------------------------------------
include $(REPO_ROOT)/scripts/makefiles/help.mk

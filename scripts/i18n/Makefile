# Orchestrates i18n extraction and translation for the osparc-simcore backend and frontend.
#
# Two SEPARATELY-OWNED catalogs (never merged into each other). Each catalog has its
# OWN symmetric set of targets so the two are kept strictly separate:
#   - Backend-owned:  packages/common-library/src/common_library/locale/messages.{pot,po,mo}
#                     = backend services user_message() + notification {% trans %} templates
#   - Frontend-owned: services/static-webserver/client/source/translation/{frontend.pot,*.po}
#                     = qooxdoo this.tr() strings (consumed directly by `qx compile`)
#
# Backend catalog (full pipeline):
#   make backend-all       # backend-extract -> backend-translate -> backend-compile
#   make backend-extract   # xgettext user_message() + jinja {% trans %} -> messages.pot (+enrich)
#   make backend-plan      # dry-run: log the LLM prompts that WOULD be sent (no call, no save)
#   make backend-translate # AI translate stale backend entries (one .po per LANG)
#   make backend-compile   # msgfmt backend .po -> .mo
#
# Frontend catalog (full pipeline):
#   make frontend-all       # frontend-extract -> frontend-translate
#   make frontend-extract   # xgettext this.tr() + json guided-tours -> frontend.pot (+enrich)
#   make frontend-plan      # dry-run: log the LLM prompts that WOULD be sent (no call, no save)
#   make frontend-translate # msgmerge + AI translate frontend catalogs from frontend.pot
#
# Translation model is selected via MODEL (default openai/gpt-4o).

REPO_ROOT      := $(shell git rev-parse --show-toplevel)
I18N_TOOLS     := $(REPO_ROOT)/scripts/i18n/tools
LOCALE_OUT_DIR := $(REPO_ROOT)/packages/common-library/src/common_library/locale
PARTIALS_DIR   := $(LOCALE_OUT_DIR)/_partials
ENV_FILE       := $(REPO_ROOT)/.env

# --- Backend configuration ---
LANGS            ?= zh_CN es_ES               ## Backend target locales (space-separated locale codes)
POT              := $(LOCALE_OUT_DIR)/messages.pot
PO_FILES         := $(foreach lang,$(LANGS),$(LOCALE_OUT_DIR)/$(lang)/LC_MESSAGES/messages.po)
MO_FILES         := $(PO_FILES:.po=.mo)
MODEL            ?= openai/gpt-4o             ## LLM model id (provider/model) used for translation
BASE_URL         ?=                           ## Custom OpenAI-compatible API base URL (empty = provider default)
PARALLEL         ?= false                     ## Translate entries in parallel
PROGRESS         ?= true                      ## Show progress bar during translation
INCREMENTAL_SAVE ?= true                      ## Save .po incrementally as entries are translated
USE_GIT          ?= true                      ## Use git blame for source-context enrichment
MAX_WORKERS      ?= 4                         ## Max parallel workers when PARALLEL=true
TRANSLATE_TS     := $(shell date +%Y%m%dT%H%M%S)

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

# --- Jinja2 templates (extracted via Babel, not xgettext) ---
# Email templates live entirely in the notifications service. Their {% trans %}
# strings are kept in the SAME backend `messages` catalog as user_message() rather
# than in a separate gettext domain. Rationale: the .mo is loaded lazily per-locale
# (functools.cache in common_library.gettext_support._load) and only by the few
# services that call get_translator (web-server, api-server, notifications); a
# few-hundred-string catalog is KB-scale, so a dedicated domain would add a second
# .pot/.po/.mo + a domain-aware get_translator for negligible memory savings.
# Follow-up trigger to revisit (split into a `notifications` domain): if the
# template catalog grows large, or services that never render emails start loading
# the catalog into memory.
NOTIFICATIONS_TEMPLATES_DIR := services/notifications/src/simcore_service_notifications/templates

# --- Frontend configuration (qooxdoo) ---
CLIENT_DIR          := $(REPO_ROOT)/services/static-webserver/client
# Repo-relative source dir: extraction runs under `cd $(REPO_ROOT)` so that the
# frontend.pot #: occurrences are repo-relative (portable + resolvable by enrich's
# git-blame), matching the backend convention instead of embedding absolute paths.
CLIENT_SRC_REL      := services/static-webserver/client/source/class
CLIENT_TRANS_DIR    := $(CLIENT_DIR)/source/translation
FRONTEND_PARTIALS_DIR := $(CLIENT_TRANS_DIR)/_partials
FRONTEND_POT        := $(CLIENT_TRANS_DIR)/frontend.pot
CLIENT_LANGS        ?= es_ES zh_CN            ## Frontend target locales (space-separated locale codes)

# --- Guided tours JSON resources (extracted via json_cmd, not xgettext) ---
# Data loaded at runtime (osparc.tours.Manager/List/Step), so their
# user-facing strings are invisible to xgettext's this.tr() scan. Only the
# listed keys hold user-facing text; id/context/anchorEl/selector/placement/
# action/beforeClick are wiring and must never be extracted.
TOURS_DIR_REL    := services/static-webserver/client/source/resource/osparc/tours
JSON_TOURS_KEYS  := name,description,title,text

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
# Step header — bold-yellow "[TAG] message" banner printed before each
# pipeline step, so Makefile-level step boundaries stay legible against the
# rich-based Python CLI's own colors (i18n_extractor.py / i18n_translator.py
# use cyan for [translate]/NEW, green for translated counts/"->", yellow
# foreground for UPDATED, and Rich auto-highlights paths/filenames in magenta
# and numbers in cyan). Bold yellow reads as "step info", not error, and
# doesn't collide with any of those. Usage: $(call STEP,TAG,message text)
# with TAG always uppercase (EXTRACT, MERGE, ENRICH, PLAN, TRANSLATE,
# COMPILE, VALIDATE).
# ---------------------------------------------------------------------------
STEP = printf '\033[1;33m[%s]\033[0m %s\n' "$(1)" "$(2)"

# ---------------------------------------------------------------------------
.DEFAULT_GOAL := help

.PHONY: backend-all backend-extract backend-plan backend-translate backend-compile \
        frontend-all frontend-extract frontend-plan frontend-translate \
        check-i18n-style clean vars

# ===========================================================================
# BACKEND catalog  (messages.pot / messages.po / messages.mo)
# ===========================================================================
backend-all: backend-extract backend-translate backend-compile  ## Backend catalog: extract -> translate -> compile

# ---------------------------------------------------------------------------
# backend-extract — gather user_message() (Python) + {% trans %} (Jinja) into
# per-source _partials/*.pot, msgcat them into messages.pot, then enrich w/ CTX.
# frontend.pot is produced separately by `frontend-extract` and never mixed in:
# mixing would leak qooxdoo strings into the backend `messages` .mo loaded by
# services.
# ---------------------------------------------------------------------------
backend-extract:  ## Extract backend user_message() + {% trans %} -> messages.pot (+enrich)
	@mkdir -p $(PARTIALS_DIR)
	@for dir in $(I18N_DIRS); do \
	  name=$$(basename $$dir); \
	  out=$(PARTIALS_DIR)/$$name.pot; \
	  $(call STEP,EXTRACT,$(REPO_ROOT)/$$dir/src -> $$out); \
	  cd $(REPO_ROOT) && $(EXTRACTOR) xgettext \
	    --src $$dir/src \
	    --out $$out \
	    --langs python; \
	done
	@$(call STEP,EXTRACT,notifications Jinja2 templates -> $(PARTIALS_DIR)/notifications-templates.pot)
	@cd $(REPO_ROOT) && $(EXTRACTOR) jinja \
	  --src $(NOTIFICATIONS_TEMPLATES_DIR) \
	  --out $(PARTIALS_DIR)/notifications-templates.pot
	@$(call STEP,MERGE,backend _partials/*.pot -> $(POT))
	@mkdir -p $(LOCALE_OUT_DIR)
	msgcat --use-first $(PARTIALS_DIR)/*.pot -o $(POT)
	@$(call STEP,ENRICH,$(POT))
	$(EXTRACTOR) enrich --pot $(POT) --repo-root $(REPO_ROOT)

# ---------------------------------------------------------------------------
# backend-plan — dry-run: compose + log the exact LLM prompts that
# backend-translate WOULD send, without calling the LLM or saving. No API key
# needed; prompts (and stub responses) are printed and appended to translate.log.
# ---------------------------------------------------------------------------
backend-plan:  ## Dry-run backend: log LLM prompts that WOULD be sent (no call, no save)
	@for lang in $(LANGS); do \
	  $(call STEP,PLAN,backend $$lang); \
	  po=$(LOCALE_OUT_DIR)/$$lang/LC_MESSAGES/messages.po; \
	  in_po_flag=""; \
	  if [ -f "$$po" ]; then in_po_flag="--in-po $$po"; fi; \
	  uv run $(I18N_TOOLS)/i18n_translator.py translate \
	    --dry-run --pot $(POT) $$in_po_flag --lang $$lang --out $$po; \
	done

# ---------------------------------------------------------------------------
# backend-translate — AI translate stale entries (one .po per LANG)
# ---------------------------------------------------------------------------
backend-translate: $(PO_FILES)  ## AI translate stale backend entries for all LANGS

$(LOCALE_OUT_DIR)/%/LC_MESSAGES/messages.po: $(POT)
	@mkdir -p $(@D)
	@if [ -f "$@" ]; then \
	  msgmerge --update --backup=none "$@" "$(POT)"; \
	else \
	  msginit --no-translator --input="$(POT)" --locale="$*" --output-file="$@"; \
	fi
	@$(call STEP,TRANSLATE,backend $* -> $@)
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
	  --log-file $(@D)/translate-$(TRANSLATE_TS).log \
	  --out $@
# ---------------------------------------------------------------------------
# backend-compile — compile .po -> .mo (backend only; the frontend catalog is
# consumed directly as .po by `qx compile` and has no .mo)
# ---------------------------------------------------------------------------
backend-compile: $(MO_FILES)  ## Compile backend .po -> .mo

$(LOCALE_OUT_DIR)/%/LC_MESSAGES/messages.mo: $(LOCALE_OUT_DIR)/%/LC_MESSAGES/messages.po
	@$(call STEP,COMPILE,$< -> $@)
	msgfmt $< -o $@

# ===========================================================================
# FRONTEND catalog  (frontend.pot / *.po — no .mo; qooxdoo reads .po directly)
# ===========================================================================
frontend-all: frontend-extract frontend-translate  ## Frontend catalog: extract -> translate

# ---------------------------------------------------------------------------
# frontend-extract — gather this.tr() (qooxdoo JS) + guided-tours JSON values
# into per-source _partials/*.pot, msgcat them into the frontend-owned
# frontend.pot, then enrich with source context. Kept strictly separate from
# the backend `messages` catalog (see header note).
# ---------------------------------------------------------------------------
frontend-extract:  ## Extract frontend this.tr() + guided-tours JSON -> frontend.pot (+enrich)
	@mkdir -p $(FRONTEND_PARTIALS_DIR)
	@$(call STEP,EXTRACT,frontend JS -> $(FRONTEND_PARTIALS_DIR)/frontend-js.pot)
	@cd $(REPO_ROOT) && $(EXTRACTOR) xgettext \
	  --src $(CLIENT_SRC_REL) \
	  --out $(FRONTEND_PARTIALS_DIR)/frontend-js.pot \
	  --langs javascript
	@$(call STEP,EXTRACT,guided tours JSON -> $(FRONTEND_PARTIALS_DIR)/frontend-tours.pot)
	@cd $(REPO_ROOT) && $(EXTRACTOR) json \
	  --src $(TOURS_DIR_REL) \
	  --keys $(JSON_TOURS_KEYS) \
	  --out $(FRONTEND_PARTIALS_DIR)/frontend-tours.pot
	@$(call STEP,MERGE,frontend _partials/*.pot -> $(FRONTEND_POT))
	msgcat --use-first $(FRONTEND_PARTIALS_DIR)/*.pot -o $(FRONTEND_POT)
	@$(call STEP,ENRICH,frontend source context -> $(FRONTEND_POT))
	@cd $(REPO_ROOT) && $(EXTRACTOR) enrich --pot $(FRONTEND_POT) --repo-root $(REPO_ROOT)

# ---------------------------------------------------------------------------
# frontend-plan — dry-run: compose + log the exact LLM prompts that
# frontend-translate WOULD send, without calling the LLM or saving.
# ---------------------------------------------------------------------------
frontend-plan:  ## Dry-run frontend: log LLM prompts that WOULD be sent (no call, no save)
	@for lang in $(CLIENT_LANGS); do \
	  case $$lang in \
	    zh_CN) out_lang=zh ;; \
	    *) out_lang=$$lang ;; \
	  esac; \
	  $(call STEP,PLAN,frontend $$lang); \
	  po=$(CLIENT_TRANS_DIR)/$$out_lang.po; \
	  in_po_flag=""; \
	  if [ -f "$$po" ]; then in_po_flag="--in-po $$po"; fi; \
	  uv run $(I18N_TOOLS)/i18n_translator.py translate \
	    --dry-run --pot $(FRONTEND_POT) $$in_po_flag --lang $$lang --out $$po; \
	done

# ---------------------------------------------------------------------------
# frontend-translate — AI translate from the frontend-owned (enriched) frontend.pot.
# CLIENT_LANGS use translation-quality locale codes (e.g. zh_CN, which the
# glossary keys on), but qooxdoo reads bare locale names (see compile.json:
# en_US, es_ES, zh). We translate as zh_CN for richer AI context + glossary yet
# write zh.po so `qx compile` picks it up. msgmerge first brings new msgids and
# the enriched CTX-SNIPPET/CTX-SNIPPET-VERSION into the .po so the translator can
# skip already-fresh entries (git-blame staleness) instead of re-spending tokens.
# ---------------------------------------------------------------------------
frontend-translate:  ## msgmerge + AI translate frontend .po files (CLIENT_LANGS) from frontend.pot
	@for lang in $(CLIENT_LANGS); do \
	  case $$lang in \
	    zh_CN) out_lang=zh ;; \
	    *) out_lang=$$lang ;; \
	  esac; \
	  out=$(CLIENT_TRANS_DIR)/$$out_lang.po; \
	  $(call STEP,TRANSLATE,frontend $$lang -> $$out); \
	  if [ -f "$$out" ]; then \
	    msgmerge --update --backup=none "$$out" "$(FRONTEND_POT)"; \
	  else \
	    msginit --no-translator --input="$(FRONTEND_POT)" --locale="$$out_lang" --output-file="$$out"; \
	  fi; \
	  uv run --env-file $(ENV_FILE) $(I18N_TOOLS)/i18n_translator.py translate \
	    --pot $(FRONTEND_POT) \
	    --in-po $$out \
	    --lang $$lang \
	    --model $(MODEL) \
	    $(BASE_URL_FLAG) \
	    $(USE_GIT_FLAG) \
	    $(INCREMENTAL_SAVE_FLAG) \
	    $(PROGRESS_FLAG) \
	    $(PARALLEL_FLAG) \
	    --max-workers $(MAX_WORKERS) \
	    --log-file $(CLIENT_TRANS_DIR)/translate-$$out_lang.log \
	    --out $$out; \
	done

# ===========================================================================
# Common (catalog-agnostic)
# ===========================================================================

# ---------------------------------------------------------------------------
# vars — list configurable variables (the ones declared with '?=' above),
# parsed straight from this file's source so the doc can never drift from the
# actual defaults. Shows the DECLARED default (not the live resolved value),
# mirroring how help.mk parses '## description' comments for targets.
# ---------------------------------------------------------------------------
vars:  ## List configurable variables (override via 'make VAR=value ...')
	@echo "Configurable variables for '$(notdir $(CURDIR))' (override via 'make VAR=value ...'):"
	@echo ""
	@grep -hE '^[A-Za-z_][A-Za-z0-9_]*[[:space:]]*\?=.*##' $(MAKEFILE_LIST) | \
	  sed -E 's/^([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*\?=[[:space:]]*(.*)##[[:space:]]*(.*)$$/\1|\2|\3/' | \
	  awk -F'|' '{gsub(/[[:space:]]+$$/, "", $$2); printf "  \033[36m%-18s\033[0m default=%-20s %s\n", $$1, ($$2==""?"(empty)":$$2), $$3}'
	@echo ""

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
check-i18n-style:  ## Validate no f-strings in user_message() calls (all I18N_DIRS)
	@for dir in $(I18N_DIRS); do \
	  $(call STEP,VALIDATE,$$dir); \
	  cd $(REPO_ROOT) && $(EXTRACTOR) validate --src $$dir/src --langs python; \
	done

# ---------------------------------------------------------------------------
# Cleanup — remove ONLY regenerable build artifacts. The .po files are
# versioned (human/AI-reviewed translations) and are NEVER deleted here.
# ---------------------------------------------------------------------------
clean:  ## Remove regenerable artifacts (_partials/, *.pot, *.mo); keeps versioned .po
	rm -rf $(PARTIALS_DIR) $(FRONTEND_PARTIALS_DIR)
	rm -f $(POT) $(FRONTEND_POT)
	rm -f $(MO_FILES)

# ---------------------------------------------------------------------------
include $(REPO_ROOT)/scripts/makefiles/help.mk

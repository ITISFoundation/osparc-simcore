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
#   make frontend-extract   # xgettext this.tr() -> frontend.pot (+enrich)
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
FRONTEND_POT        := $(CLIENT_TRANS_DIR)/frontend.pot
CLIENT_LANGS        ?= es_ES zh_CN

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

.PHONY: backend-all backend-extract backend-plan backend-translate backend-compile \
        frontend-all frontend-extract frontend-plan frontend-translate \
        check-i18n-style clean

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
	  echo "  [extract] $(REPO_ROOT)/$$dir/src -> $$out"; \
	  cd $(REPO_ROOT) && $(EXTRACTOR) xgettext \
	    --src $$dir/src \
	    --out $$out \
	    --langs python; \
	done
	@echo "  [extract] notifications Jinja2 templates -> $(PARTIALS_DIR)/notifications-templates.pot"
	@cd $(REPO_ROOT) && $(EXTRACTOR) jinja \
	  --src $(NOTIFICATIONS_TEMPLATES_DIR) \
	  --out $(PARTIALS_DIR)/notifications-templates.pot
	@echo "  [merge] backend _partials/*.pot -> $(POT)"
	@mkdir -p $(LOCALE_OUT_DIR)
	msgcat --use-first $(PARTIALS_DIR)/*.pot -o $(POT)
	$(EXTRACTOR) enrich --pot $(POT) --repo-root $(REPO_ROOT)

# ---------------------------------------------------------------------------
# backend-plan — dry-run: compose + log the exact LLM prompts that
# backend-translate WOULD send, without calling the LLM or saving. No API key
# needed; prompts (and stub responses) are printed and appended to translate.log.
# ---------------------------------------------------------------------------
backend-plan:  ## Dry-run backend: log LLM prompts that WOULD be sent (no call, no save)
	@for lang in $(LANGS); do \
	  echo "  [plan] backend $$lang"; \
	  po=$(LOCALE_OUT_DIR)/$$lang/LC_MESSAGES/messages.po; \
	  in_po_flag=""; \
	  if [ -f "$$po" ]; then in_po_flag="--in-po $$po"; fi; \
	  uv run $(I18N_TOOLS)/i18n_translator.py translate \
	    --plan --pot $(POT) $$in_po_flag --lang $$lang --out $$po; \
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
	msgfmt $< -o $@

# ===========================================================================
# FRONTEND catalog  (frontend.pot / *.po — no .mo; qooxdoo reads .po directly)
# ===========================================================================
frontend-all: frontend-extract frontend-translate  ## Frontend catalog: extract -> translate

# ---------------------------------------------------------------------------
# frontend-extract — extract this.tr() strings from qooxdoo frontend into the
# frontend-owned frontend.pot, then enrich with source context.
# ---------------------------------------------------------------------------
frontend-extract:  ## Extract frontend this.tr() -> frontend.pot (+enrich)
	@echo "  [extract] frontend JS -> $(FRONTEND_POT)"
	@mkdir -p $(CLIENT_TRANS_DIR)
	@cd $(REPO_ROOT) && $(EXTRACTOR) xgettext \
	  --src $(CLIENT_SRC_REL) \
	  --out $(FRONTEND_POT) \
	  --langs javascript
	@echo "  [enrich] frontend source context -> $(FRONTEND_POT)"
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
	  echo "  [plan] frontend $$lang"; \
	  po=$(CLIENT_TRANS_DIR)/$$out_lang.po; \
	  in_po_flag=""; \
	  if [ -f "$$po" ]; then in_po_flag="--in-po $$po"; fi; \
	  uv run $(I18N_TOOLS)/i18n_translator.py translate \
	    --plan --pot $(FRONTEND_POT) $$in_po_flag --lang $$lang --out $$po; \
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
	  echo "  [translate] frontend $$lang -> $$out"; \
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
# Validation
# ---------------------------------------------------------------------------
check-i18n-style:  ## Validate no f-strings in user_message() calls (all I18N_DIRS)
	@for dir in $(I18N_DIRS); do \
	  echo "  [validate] $$dir"; \
	  cd $(REPO_ROOT) && $(EXTRACTOR) validate --src $$dir/src --langs python; \
	done

# ---------------------------------------------------------------------------
# Cleanup — remove ONLY regenerable build artifacts. The .po files are
# versioned (human/AI-reviewed translations) and are NEVER deleted here.
# ---------------------------------------------------------------------------
clean:  ## Remove regenerable artifacts (_partials/, *.pot, *.mo); keeps versioned .po
	rm -rf $(PARTIALS_DIR)
	rm -f $(POT) $(FRONTEND_POT)
	rm -f $(MO_FILES)

# ---------------------------------------------------------------------------
include $(REPO_ROOT)/scripts/makefiles/help.mk

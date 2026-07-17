### i18n/tools/ollama.mk — reusable local Ollama daemon management.
###
### Include with: include /path/to/i18n/tools/ollama.mk  (see ../Makefile for an
### example of the "set vars, then include" pattern used to override defaults.)
###
### Deliberately provider/model-naming AGNOSTIC (no litellm `ollama/<tag>` prefix
### knowledge, no translation-specific logic) so it can be included as-is from any
### Makefile that wants a local Ollama daemon (not just ../Makefile).
###
### Overridable vars (set BEFORE the `include` line so the `?=` defaults below
### become no-ops):
###   OLLAMA_HOST            -- daemon URL (health-check + API base)
###   OLLAMA_MODEL           -- tag `ollama-pull`/`ollama-ensure` act on
###   OLLAMA_STARTUP_TIMEOUT -- seconds to wait for `ollama serve` to become healthy
###   OLLAMA_STATE_DIR       -- PID/log file location
###
### Targets (each independently runnable):
###   ollama-status  -- health-check $(OLLAMA_HOST); non-destructive
###   ollama-serve   -- idempotent background start; skip if already reachable
###   ollama-stop    -- stop ONLY the daemon THIS Makefile started (PID file)
###   ollama-pull    -- `ollama pull $(OLLAMA_MODEL)`
###   ollama-ensure  -- serve + pull $(OLLAMA_MODEL); use this as a prerequisite
###
### \note A local Ollama daemon is a single machine-wide process (one port,
### 11434 by default) shared by whichever Makefile starts it -- it is NOT
### per-repo state. PID/log files therefore default under /tmp, not a
### repo-tracked directory (avoids repo pollution / gitignore churn, and
### reflects the shared-daemon reality: two Makefiles both running
### `ollama-serve` should coordinate on the SAME daemon, not start two).

OLLAMA_HOST            ?= http://localhost:11434   ## Ollama daemon URL (health-check + API base)
OLLAMA_MODEL           ?= llama3.1                  ## Model tag for `ollama-pull`/`ollama-ensure` (set before include to override)
OLLAMA_STARTUP_TIMEOUT ?= 30                        ## Seconds to wait for `ollama serve` to become healthy
OLLAMA_STATE_DIR       ?= /tmp/s4l-ollama-mk         ## PID/log file location (shared across includers -- see note above)

# \note re-assign with $(strip ...): the column-aligned `##` comments above leave
# trailing whitespace IN the value itself (make only strips the comment, not
# whitespace before it). Left unstripped, direct concatenations below (e.g.
# `$(OLLAMA_HOST)/api/tags`, `>$(OLLAMA_LOG_FILE)`) would silently split into
# multiple shell words/wrong paths. Normalize once here so every use downstream
# is safe.
OLLAMA_HOST            := $(strip $(OLLAMA_HOST))
OLLAMA_MODEL           := $(strip $(OLLAMA_MODEL))
OLLAMA_STARTUP_TIMEOUT := $(strip $(OLLAMA_STARTUP_TIMEOUT))
OLLAMA_STATE_DIR       := $(strip $(OLLAMA_STATE_DIR))

OLLAMA_PID_FILE := $(OLLAMA_STATE_DIR)/ollama.pid
OLLAMA_LOG_FILE := $(OLLAMA_STATE_DIR)/ollama.log

.PHONY: ollama-status ollama-serve ollama-stop ollama-pull ollama-ensure

# ---------------------------------------------------------------------------
ollama-status: ## Health-check the local Ollama daemon
	@if curl -fsS $(OLLAMA_HOST)/api/tags >/dev/null 2>&1; then \
	  echo "[ollama] reachable at $(OLLAMA_HOST)"; \
	else \
	  echo "[ollama] NOT reachable at $(OLLAMA_HOST)"; exit 1; \
	fi

# ---------------------------------------------------------------------------
ollama-serve: ## Start local Ollama daemon in background (idempotent)
	@mkdir -p $(OLLAMA_STATE_DIR)
	@if curl -fsS $(OLLAMA_HOST)/api/tags >/dev/null 2>&1; then \
	  echo "[ollama] already reachable at $(OLLAMA_HOST) -- not starting a new daemon"; \
	  exit 0; \
	fi
	@command -v ollama >/dev/null 2>&1 || { \
	  echo "[error] 'ollama' CLI not found -- install from https://ollama.com/download"; exit 1; \
	}
	@echo "[ollama] starting 'ollama serve' in background (log: $(OLLAMA_LOG_FILE))"
	@nohup ollama serve >$(OLLAMA_LOG_FILE) 2>&1 & echo $$! >$(OLLAMA_PID_FILE)
	@for i in $$(seq 1 $(OLLAMA_STARTUP_TIMEOUT)); do \
	  curl -fsS $(OLLAMA_HOST)/api/tags >/dev/null 2>&1 && { echo "[ollama] up (pid $$(cat $(OLLAMA_PID_FILE)))"; exit 0; }; \
	  sleep 1; \
	done; \
	echo "[error] ollama serve did not become healthy within $(OLLAMA_STARTUP_TIMEOUT)s -- see $(OLLAMA_LOG_FILE)"; exit 1

# ---------------------------------------------------------------------------
ollama-stop: ## Stop the Ollama daemon started by this Makefile
	@if [ -f $(OLLAMA_PID_FILE) ]; then \
	  kill $$(cat $(OLLAMA_PID_FILE)) 2>/dev/null || true; \
	  rm -f $(OLLAMA_PID_FILE); \
	  echo "[ollama] stopped"; \
	else \
	  echo "[ollama] no PID file -- nothing to stop (daemon may be externally managed)"; \
	fi

# ---------------------------------------------------------------------------
ollama-pull: | ollama-serve ## Pull the Ollama model (OLLAMA_MODEL=$(OLLAMA_MODEL))
	@echo "[ollama] pull $(OLLAMA_MODEL)"
	ollama pull $(OLLAMA_MODEL)

# ---------------------------------------------------------------------------
ollama-ensure: ollama-pull ## Ensure Ollama daemon is running with model pulled

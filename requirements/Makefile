# Makefile for Python dependency workflows
#
# Central entry point for all repo-wide and project-scoped Python dependency
# management tasks. Wraps existing scripts and tools for a consistent interface.
#
# See requirements/python-dependencies.md for comprehensive workflow documentation.
#
# ═════════════════════════════════════════════════════════════════════════════
# USAGE
# ═════════════════════════════════════════════════════════════════════════════
#
# Repo-wide security fix:
#   make security-fix PKG=aiohttp VERSION=">=3.11.14" CVE_ID=CVE-2024-23334
#
# Project-scoped security fix (still updates global constraint; regeneration scoped):
#   make security-fix PKG=aiohttp VERSION=">=3.11.14" SCOPE=services/web
#
# Non-interactive (for CI/agents):
#   make security-fix PKG=aiohttp VERSION=">=3.11.14" INTERACTIVE=false
#
# Help:
#   make help
#

.PHONY: help
.DEFAULT_GOAL := help

REPO_ROOT := $(shell git rev-parse --show-toplevel)
SCRIPT_DIR := $(REPO_ROOT)/requirements/scripts
CONSTRAINTS_FILE := $(REPO_ROOT)/requirements/constraints.txt

# ═════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ═════════════════════════════════════════════════════════════════════════════

# check_required <VAR_NAME> — Error if parameter is empty
define check_required
	@if [ -z "$($(1))" ]; then \
		echo "Error: $(1) is required but empty"; \
		echo ""; \
		$(MAKE) help; \
		exit 1; \
	fi
endef

# check_optional <VAR_NAME> — No error if empty (used for optional params)
define check_optional
	@true
endef

# ═════════════════════════════════════════════════════════════════════════════
# security-fix: Apply security constraint and regenerate *.txt files
# ═════════════════════════════════════════════════════════════════════════════
#
# Parameters:
#   PKG          Package name, e.g. "aiohttp" (required)
#   VERSION      pip version constraint, e.g. ">=3.11.14" (required)
#   CVE_ID       Optional CVE/GHSA id, e.g. "CVE-2024-23334" (optional)
#   SCOPE        Optional project scope, e.g. "services/web" for reporting (optional)
#   INTERACTIVE  "true" (default) or "false" for --yes flag (optional)
#
# Examples:
#   make security-fix PKG=aiohttp VERSION=">=3.11.14"
#   make security-fix PKG=aiohttp VERSION=">=3.11.14" CVE_ID=CVE-2024-23334
#   make security-fix PKG=cryptography VERSION=">=43.0.1" SCOPE=services/api-server
#   make security-fix PKG=aiohttp VERSION=">=3.11.14" INTERACTIVE=false
#

.PHONY: security-fix
security-fix: _validate-security-fix-params _run-security-fix

.PHONY: _validate-security-fix-params
_validate-security-fix-params:
	$(call check_required,PKG)
	$(call check_required,VERSION)
	@echo "🔍 Validating parameters..."
	@if ! echo "$(PKG)" | grep -qE '^[A-Za-z0-9._-]+$$'; then \
		echo "Error: PKG='$(PKG)' contains invalid characters"; \
		echo "  Package name must contain only alphanumeric, dots, dashes, underscores"; \
		exit 1; \
	fi
	@if ! echo "$(VERSION)" | grep -qE '^[><=!~]'; then \
		echo "Error: VERSION='$(VERSION)' does not start with comparison operator"; \
		echo "  Valid operators: >, <, >=, <=, ==, !=, ~="; \
		exit 1; \
	fi
	@echo "  PKG:      $(PKG)"
	@echo "  VERSION:  $(VERSION)"
	@if [ -n "$(CVE_ID)" ]; then echo "  CVE_ID:   $(CVE_ID)"; fi
	@if [ -n "$(SCOPE)" ]; then echo "  SCOPE:    $(SCOPE)"; fi
	@echo "  ✓ Validation passed"

.PHONY: _run-security-fix
_run-security-fix:
	@echo ""
	@echo "▶ Running security fix workflow..."
	@echo ""
	@INTERACTIVE_FLAG=""; \
	if [ "$(INTERACTIVE)" = "false" ]; then \
		INTERACTIVE_FLAG="--yes"; \
	fi; \
	$(SCRIPT_DIR)/propagate-security-fix.sh $${INTERACTIVE_FLAG} "$(PKG)" "$(VERSION)" "$(CVE_ID)"
	@echo ""
	@echo "✓ Security fix applied."
	@if [ -n "$(SCOPE)" ]; then \
		echo "  Note: constraint applies repo-wide; regeneration scoped to $(SCOPE)"; \
	else \
		echo "  Note: constraint and regeneration applied repo-wide"; \
	fi
	@echo ""
	@echo "Next steps:"; \
	echo "  1. Review the diff:  git diff requirements/"; \
	echo "  2. Run tests:        make tests-unit"; \
	echo "  3. Commit:           git add requirements/ && git commit -m 'fix(deps): $(PKG)$(VERSION)'"; \
	echo ""

# ═════════════════════════════════════════════════════════════════════════════
# audit: Scan dependencies for known CVEs using pip-audit
# ═════════════════════════════════════════════════════════════════════════════
#
# Runs security scanning on production and/or test dependencies.
# Mirrors the CI workflow from .github/workflows/pip-audit.yml for local testing.
#
# Parameters:
#   SCOPE    Optional: scan only specific project/service (e.g., services/catalog,
#            services/*, packages/models-library). If omitted, scans all projects.
#
# Examples:
#   make audit                          # Scan all (prod + test)
#   make audit-prod                     # Scan production deps only — fails on CVE
#   make audit-test                     # Scan test deps only — warnings only
#   make audit SCOPE=services/catalog   # Scan catalog service only
#   make audit SCOPE=services/*         # Scan all services
#

.PHONY: audit
audit: audit-prod audit-test ## Scan all dependencies for CVEs (prod + test)

.PHONY: audit-prod
audit-prod: _check-uv ## Scan production deps (_base.txt) — fails on CVE
	@echo ""
	@if [ -n "$(SCOPE)" ]; then \
		echo "🔍 Scanning production dependencies for CVEs in $(SCOPE) (CI will fail if found)..."; \
	else \
		echo "🔍 Scanning production dependencies for CVEs (CI will fail if found)..."; \
	fi
	@echo ""
	@FIND_PATH="$(REPO_ROOT)"; \
	if [ -n "$(SCOPE)" ]; then \
		FIND_PATH="$(REPO_ROOT)/$(SCOPE)"; \
	fi; \
	BASE_FILES=$$(find $$FIND_PATH -name '_base.txt' -path '*/requirements/*' 2>/dev/null | sort); \
	if [ -z "$$BASE_FILES" ]; then \
		echo "⚠️  No _base.txt files found"; \
		exit 0; \
	fi; \
	UV_CMD=$$(command -v uv || echo "$(HOME)/.local/bin/uv"); \
	FAILED=0; \
	for f in $$BASE_FILES; do \
		echo "  📋 Auditing: $$f"; \
		if ! "$$UV_CMD" run --with pip-audit pip-audit -r "$$f" --skip-editable --no-deps; then \
			FAILED=1; \
		fi; \
	done; \
	if [ $$FAILED -eq 1 ]; then \
		echo ""; \
		echo "❌ CVEs found in production dependencies"; \
		exit 1; \
	fi
	@echo ""
	@echo "✅ No vulnerabilities found in production dependencies"
	@echo ""

.PHONY: audit-test
audit-test: _check-uv ## Scan test deps (_test.txt) — warnings only
	@echo ""
	@if [ -n "$(SCOPE)" ]; then \
		echo "🔍 Scanning test dependencies for CVEs in $(SCOPE) (warnings only, never blocks)..."; \
	else \
		echo "🔍 Scanning test dependencies for CVEs (warnings only, never blocks)..."; \
	fi
	@echo ""
	@FIND_PATH="$(REPO_ROOT)"; \
	if [ -n "$(SCOPE)" ]; then \
		FIND_PATH="$(REPO_ROOT)/$(SCOPE)"; \
	fi; \
	TEST_FILES=$$(find $$FIND_PATH -name '_test.txt' -path '*/requirements/*' 2>/dev/null | sort); \
	if [ -z "$$TEST_FILES" ]; then \
		echo "ℹ️  No _test.txt files found"; \
		exit 0; \
	fi; \
	UV_CMD=$$(command -v uv || echo "$(HOME)/.local/bin/uv"); \
	for f in $$TEST_FILES; do \
		echo "  📋 Auditing: $$f"; \
		"$$UV_CMD" run --with pip-audit pip-audit -r "$$f" --skip-editable --no-deps || true; \
	done
	@echo ""
	@echo "⚠️  Test-only CVEs are informational; they do not block CI"
	@echo ""

.PHONY: _check-uv
_check-uv:
	@if ! command -v uv &> /dev/null && ! [ -x "$${HOME}/.local/bin/uv" ]; then \
		echo "❌ Error: uv not found"; \
		echo ""; \
		echo "Install uv: https://docs.astral.sh/uv/getting-started/installation/"; \
		exit 1; \
	fi

# ═════════════════════════════════════════════════════════════════════════════
# prune-deps: Detect and remove unused Python dependencies
# ═════════════════════════════════════════════════════════════════════════════
#
# Three-phase workflow to identify and safely remove unused dependencies:
#   1. detect  — Run deptry to find unused deps, store findings
#   2. confirm — Review findings, manually approve removals
#   3. finalize — Recompile and propagate to downstream packages
#
# Parameters:
#   SCOPE       Optional: single package/service path (e.g., packages/common-library)
#   ALL         Optional: set to "true" to scan all packages (defaults to false)
#   INTERACTIVE Optional: set to "false" to skip prompts (defaults to true)
#
# Single package (default):
#   make prune-deps SCOPE=packages/common-library
#   make prune-deps SCOPE=services/catalog
#
# Repo-wide (all packages and services):
#   make prune-deps ALL=true
#
# Non-interactive (for CI/agents):
#   make prune-deps SCOPE=packages/common-library INTERACTIVE=false
#

.PHONY: prune-deps
prune-deps: _validate-prune-deps-params _prune-deps-detect

.PHONY: prune-deps-all
prune-deps-all: _prune-deps-detect-all

.PHONY: _validate-prune-deps-params
_validate-prune-deps-params:
	@echo "🔍 Validating prune-deps parameters..."
	@if [ "$(ALL)" = "true" ]; then \
		echo "  Mode:         Repo-wide (all packages and services)"; \
	elif [ -n "$(SCOPE)" ]; then \
		if [ ! -d "$(REPO_ROOT)/$(SCOPE)" ]; then \
			echo "Error: SCOPE='$(SCOPE)' does not exist"; \
			exit 1; \
		fi; \
		if [ ! -f "$(REPO_ROOT)/$(SCOPE)/requirements/_base.in" ]; then \
			echo "Error: SCOPE='$(SCOPE)' does not have requirements/_base.in"; \
			exit 1; \
		fi; \
		echo "  SCOPE:        $(SCOPE)"; \
	else \
		echo "Error: SCOPE is required (or set ALL=true for repo-wide)"; \
		exit 1; \
	fi
	@if [ "$(INTERACTIVE)" = "false" ]; then \
		echo "  Interactive:  false (skip all prompts)"; \
	else \
		echo "  Interactive:  true (prompt at each phase)"; \
	fi
	@echo "  ✓ Validation passed"

.PHONY: _prune-deps-detect
_prune-deps-detect: _check-uv
	@echo ""
	@echo "▶ Phase 1: Detect unused dependencies..."
	@echo ""
	@SCOPE_PATH="$(REPO_ROOT)/$(SCOPE)"; \
	if [ ! -d "$$SCOPE_PATH" ]; then \
		echo "❌ Error: Path does not exist: $$SCOPE_PATH"; \
		exit 1; \
	fi; \
	if [ ! -f "$$SCOPE_PATH/requirements/_base.in" ]; then \
		echo "❌ Error: No requirements/_base.in found in $(SCOPE)"; \
		exit 1; \
	fi; \
	cd "$$SCOPE_PATH" || exit 1; \
	PKG_NAME=$$(basename $$SCOPE_PATH | sed 's/-/_/g'); \
	echo "  📦 Package: $(SCOPE)"; \
	echo "  🔎 Running deptry..."; \
	echo ""; \
	if uvx deptry src tests \
		--requirements-files requirements/_base.in \
		--requirements-files-dev requirements/_test.in \
		--known-first-party $$PKG_NAME 2>&1 | tee /tmp/deptry-output.txt; then \
		echo ""; \
		echo "  ✓ No unused dependencies found."; \
	else \
		UNUSED_FOUND=$$(grep -c "DEP002" /tmp/deptry-output.txt 2>/dev/null || echo 0); \
		if [ $$UNUSED_FOUND -gt 0 ]; then \
			echo ""; \
			echo "  ⚠️  Found unused dependencies (DEP002):"; \
			grep "DEP002" /tmp/deptry-output.txt | head -20; \
			echo ""; \
			if [ "$(INTERACTIVE)" = "true" ]; then \
				read -p "  Continue to confirmation phase? (y/n) " CONT; \
				if [ "$$CONT" != "y" ]; then \
					echo "  Cancelled by user."; \
					exit 0; \
				fi; \
			fi; \
			$(MAKE) _prune-deps-confirm SCOPE="$(SCOPE)" INTERACTIVE="$(INTERACTIVE)"; \
		else \
			echo "  ✓ No unused dependencies found."; \
		fi; \
	fi

.PHONY: _prune-deps-detect-all
_prune-deps-detect-all: _check-uv
	@echo ""
	@echo "▶ Phase 1: Detect unused dependencies (repo-wide)..."
	@echo ""
	@PKG_COUNT=0; \
	UNUSED_COUNT=0; \
	for pkg_dir in $$(find $(REPO_ROOT)/packages $(REPO_ROOT)/services -maxdepth 2 -name _base.in -path '*/requirements/*' 2>/dev/null | xargs dirname | sort); do \
		PKG_PATH=$$(echo $$pkg_dir | sed 's|/requirements||'); \
		SCOPE=$${PKG_PATH#$(REPO_ROOT)/}; \
		PKG_COUNT=$$((PKG_COUNT + 1)); \
		echo ""; \
		echo "  [$$PKG_COUNT] Scanning: $$SCOPE"; \
		$(MAKE) _prune-deps-detect SCOPE="$$SCOPE" INTERACTIVE="false" || true; \
		UNUSED_COUNT=$$((UNUSED_COUNT + 1)); \
	done; \
	echo ""; \
	echo "✓ Repo-wide scan complete (checked $$PKG_COUNT packages)"

.PHONY: _prune-deps-confirm
_prune-deps-confirm:
	@echo ""
	@echo "▶ Phase 2: Confirm removals..."
	@echo ""
	@SCOPE_PATH="$(REPO_ROOT)/$(SCOPE)"; \
	echo "  📝 To remove unused dependencies from $(SCOPE):"; \
	echo ""; \
	echo "  1. Edit file: $$SCOPE_PATH/requirements/_base.in"; \
	echo "     Remove lines corresponding to DEP002 findings above."; \
	echo ""; \
	echo "  2. Also check: $$SCOPE_PATH/requirements/_test.in"; \
	echo "     Remove any unused test-only dependencies."; \
	echo ""; \
	if [ "$(INTERACTIVE)" = "true" ]; then \
		read -p "  Press Enter when done editing files, or Ctrl+C to cancel..."; \
	fi; \
	echo ""; \
	echo "  Proceeding to finalization phase..."; \
	$(MAKE) _prune-deps-finalize SCOPE="$(SCOPE)" INTERACTIVE="$(INTERACTIVE)"

.PHONY: _prune-deps-finalize
_prune-deps-finalize: _check-uv
	@echo ""
	@echo "▶ Phase 3: Finalize and propagate..."
	@echo ""
	@SCOPE_PATH="$(REPO_ROOT)/$(SCOPE)"; \
	cd "$$SCOPE_PATH/requirements" || exit 1; \
	echo "  🔄 Recompiling requirements..."; \
	if make touch reqs 2>&1 | tail -10; then \
		echo ""; \
		echo "  ✓ Recompilation successful."; \
	else \
		echo ""; \
		echo "  ⚠️  Recompilation failed. Check removed dependencies."; \
		exit 1; \
	fi; \
	echo ""; \
	echo "  🔍 Detecting downstream packages..."; \
	DEPENDENTS=$$(grep -l "$(SCOPE)/requirements/_base.in" $(REPO_ROOT)/packages/*/requirements/_base.in $(REPO_ROOT)/services/*/requirements/_base.in 2>/dev/null | xargs dirname | sed 's|/requirements||' | sed "s|$(REPO_ROOT)/||" | sort); \
	if [ -z "$$DEPENDENTS" ]; then \
		echo "  ℹ️  No downstream dependencies found."; \
	else \
		echo "  Found downstream packages:"; \
		echo "$$DEPENDENTS" | sed 's/^/    - /'; \
		echo ""; \
		if [ "$(INTERACTIVE)" = "true" ]; then \
			echo "  Downstream packages will be regenerated with minimal changes."; \
			echo "  (Only updated transitive dependencies from the pruned package.)"; \
			echo ""; \
			read -p "  Regenerate downstream packages? (y/n) " REGEN; \
			if [ "$$REGEN" = "y" ]; then \
				for dep in $$DEPENDENTS; do \
					echo ""; \
					echo "    ↻ Regenerating: $$dep"; \
					DEP_PKG=$$(echo "$$dep" | sed 's|.*/||'); \
					cd "$(REPO_ROOT)/$$dep/requirements" 2>/dev/null && make touch reqs upgrade="$$(echo $(SCOPE) | sed 's|.*/||')" || true; \
				done; \
			fi; \
		else \
			for dep in $$DEPENDENTS; do \
				echo "    ↻ Regenerating: $$dep"; \
				cd "$(REPO_ROOT)/$$dep/requirements" 2>/dev/null && make touch reqs upgrade="$$(echo $(SCOPE) | sed 's|.*/||')" || true; \
			done; \
		fi; \
	fi; \
	echo ""; \
	echo "✓ Pruning workflow complete!"; \
	echo ""; \
	echo "Next steps:"; \
	echo "  1. Review the diff:  git diff requirements/"; \
	echo "  2. Run tests:        make install-dev && make tests-unit"; \
	echo "  3. Commit:           git add requirements/ && git commit -m 'chore(deps): prune unused from $(SCOPE)'"; \
	echo ""

# ═════════════════════════════════════════════════════════════════════════════
# help: Display available workflows and usage
# ═════════════════════════════════════════════════════════════════════════════

help: ## Display help for Python dependency workflows
	@echo ""
	@echo "═══════════════════════════════════════════════════════════════════════════════"
	@echo "  Python Dependency Workflows"
	@echo "═══════════════════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "CURRENT WORKFLOWS:"
	@echo ""
	@echo "  1. audit — Scan dependencies for known CVEs using pip-audit (via uv)"
	@echo "     Usage:"
	@echo "       make audit              # Scan all (production + test deps)"
	@echo "       make audit-prod         # Scan production deps only (fails on CVE)"
	@echo "       make audit-test         # Scan test deps only (warnings only)"
	@echo ""
	@echo "     Optional Parameters:"
	@echo "       SCOPE       Scan specific project/service (e.g., services/catalog, services/*, packages/models-library)"
	@echo ""
	@echo "     Notes:"
	@echo "       - Uses 'uv run --with pip-audit' (no installation required)"
	@echo "       - Requires: uv >= 0.1.0 (already part of repo setup)"
	@echo ""
	@echo "     Examples:"
	@echo "       # Local security audit before committing"
	@echo "       make audit"
	@echo ""
	@echo "       # CI-like check: production deps only"
	@echo "       make audit-prod"
	@echo ""
	@echo "       # Audit specific service"
	@echo "       make audit SCOPE=services/catalog"
	@echo ""
	@echo "       # Audit all services (production deps only)"
	@echo "       make audit-prod SCOPE=services/*"
	@echo ""
	@echo "───────────────────────────────────────────────────────────────────────────────"
	@echo ""
	@echo "  2. security-fix — Apply security constraint and regenerate all *.txt files"
	@echo "     Usage:"
	@echo "       make security-fix PKG=<package> VERSION=<constraint> [options]"
	@echo ""
	@echo "     Required Parameters:"
	@echo "       PKG         Package name (e.g., aiohttp, cryptography)"
	@echo "       VERSION     pip version constraint (e.g., >=3.11.14, ==43.0.1)"
	@echo ""
	@echo "     Optional Parameters:"
	@echo "       CVE_ID      CVE or GHSA id (e.g., CVE-2024-23334)"
	@echo "       SCOPE       Project scope for reporting (e.g., services/web)"
	@echo "       INTERACTIVE false to skip prompts (default: true)"
	@echo ""
	@echo "     Examples:"
	@echo "       # Repo-wide security fix"
	@echo "       make security-fix PKG=aiohttp VERSION='>=3.11.14'"
	@echo ""
	@echo "       # With CVE tracking"
	@echo "       make security-fix PKG=aiohttp VERSION='>=3.11.14' CVE_ID=CVE-2024-23334"
	@echo ""
	@echo "       # Project-scoped (constraint still applies repo-wide)"
	@echo "       make security-fix PKG=cryptography VERSION='>=43.0.1' SCOPE=services/api-server"
	@echo ""
	@echo "       # Non-interactive (for CI/agents)"
	@echo "       make security-fix PKG=aiohttp VERSION='>=3.11.14' INTERACTIVE=false"
	@echo ""
	@echo "───────────────────────────────────────────────────────────────────────────────"
	@echo ""
	@echo "  3. prune-deps — Detect and remove unused dependencies (via deptry)"
	@echo "     Usage:"
	@echo "       make prune-deps SCOPE=<pkg>         # Single package (3 phases, interactive)"
	@echo "       make prune-deps-all                 # Repo-wide scan (detect phase only)"
	@echo ""
	@echo "     Workflow Phases:"
	@echo "       Phase 1 (detect)   — Run deptry to find unused deps (DEP002)"
	@echo "       Phase 2 (confirm)  — Manually edit *.in files to approve removals"
	@echo "       Phase 3 (finalize) — Recompile and propagate to downstream packages"
	@echo ""
	@echo "     Required Parameters:"
	@echo "       SCOPE     Package/service path (e.g., packages/common-library, services/catalog)"
	@echo ""
	@echo "     Optional Parameters:"
	@echo "       ALL         Set to 'true' to scan all packages (default: false)"
	@echo "       INTERACTIVE Set to 'false' to skip prompts (default: true)"
	@echo ""
	@echo "     Notes:"
	@echo "       - Phases run automatically in sequence"
	@echo "       - Phase 2 pauses to let you edit _base.in and _test.in files"
	@echo "       - Phase 3 auto-detects and regenerates affected downstream packages"
	@echo "       - Uses 'uvx deptry' (no installation required)"
	@echo "       - Requires: uv >= 0.1.0 (already part of repo setup)"
	@echo ""
	@echo "     Examples:"
	@echo "       # Prune single package (interactive, 3 phases)"
	@echo "       make prune-deps SCOPE=packages/common-library"
	@echo ""
	@echo "       # Scan repo-wide for unused deps (detection only, non-interactive)"
	@echo "       make prune-deps-all"
	@echo ""
	@echo "       # Non-interactive (for CI/agents)"
	@echo "       make prune-deps SCOPE=packages/service-library INTERACTIVE=false"
	@echo ""
	@echo "───────────────────────────────────────────────────────────────────────────────"
	@echo ""
	@echo "FUTURE WORKFLOWS (coming soon):"
	@echo ""
	@echo "  - python-upgrade    Update Python version across repo"
	@echo "  - test-deps-update  Update test-only dependencies"
	@echo ""
	@echo "───────────────────────────────────────────────────────────────────────────────"
	@echo ""
	@echo "ARCHITECTURE:"
	@echo ""
	@echo "  requirements/                           # Repo root for all dependency work"
	@echo "    constraints.txt                       # Central security constraint layer"
	@echo "    scripts/propagate-security-fix.sh     # Engine for security fixes"
	@echo "    tools/Makefile                        # Batch operations (reqs-all, etc.)"
	@echo "    python-dependencies.md                # Complete workflow documentation"
	@echo ""
	@echo "  For comprehensive documentation, see: requirements/python-dependencies.md"
	@echo ""
	@echo "═══════════════════════════════════════════════════════════════════════════════"
	@echo ""

# ═════════════════════════════════════════════════════════════════════════════
# FUTURE: Placeholder targets for extensibility
# ═════════════════════════════════════════════════════════════════════════════
# These will be implemented as separate workflows grow:
#
# .PHONY: python-upgrade
# python-upgrade: _validate-python-upgrade-params _run-python-upgrade
#   # Update Python version repo-wide
#   # Parameters: PYTHON_VERSION (required)
#   # Example: make python-upgrade PYTHON_VERSION=3.14
#
# .PHONY: test-deps-update
# test-deps-update: _validate-test-deps-update-params _run-test-deps-update
#   # Update test-only dependencies
#   # Parameters: PACKAGE (optional for single pkg or leave empty for all)
#   # Example: make test-deps-update PACKAGE=pytest
#

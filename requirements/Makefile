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
# Examples:
#   make audit              # Scan all (prod + test)
#   make audit-prod         # Scan production deps only (_base.txt) — fails on CVE
#   make audit-test         # Scan test deps only (_test.txt) — warnings only
#

.PHONY: audit
audit: audit-prod audit-test ## Scan all dependencies for CVEs (prod + test)

.PHONY: audit-prod
audit-prod: _check-uv ## Scan production deps (_base.txt) — fails on CVE
	@echo ""
	@echo "🔍 Scanning production dependencies for CVEs (CI will fail if found)..."
	@echo ""
	@BASE_FILES=$$(find $(REPO_ROOT) -name '_base.txt' -path '*/requirements/*' | sort); \
	if [ -z "$$BASE_FILES" ]; then \
		echo "⚠️  No _base.txt files found"; \
		exit 0; \
	fi; \
	UV_CMD=$$(command -v uv || echo "$(HOME)/.local/bin/uv"); \
	REQ_ARGS=""; \
	for f in $$BASE_FILES; do \
		REQ_ARGS="$$REQ_ARGS -r $$f"; \
	done; \
	"$$UV_CMD" run --with pip-audit pip-audit $$REQ_ARGS --skip-editable --no-deps || exit 1
	@echo ""
	@echo "✅ No vulnerabilities found in production dependencies"
	@echo ""

.PHONY: audit-test
audit-test: _check-uv ## Scan test deps (_test.txt) — warnings only
	@echo ""
	@echo "🔍 Scanning test dependencies for CVEs (warnings only, never blocks)..."
	@echo ""
	@TEST_FILES=$$(find $(REPO_ROOT) -name '_test.txt' -path '*/requirements/*' | sort); \
	if [ -z "$$TEST_FILES" ]; then \
		echo "ℹ️  No _test.txt files found"; \
		exit 0; \
	fi; \
	UV_CMD=$$(command -v uv || echo "$(HOME)/.local/bin/uv"); \
	REQ_ARGS=""; \
	for f in $$TEST_FILES; do \
		REQ_ARGS="$$REQ_ARGS -r $$f"; \
	done; \
	"$$UV_CMD" run --with pip-audit pip-audit $$REQ_ARGS --skip-editable --no-deps || true
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
	@echo "FUTURE WORKFLOWS (coming soon):"
	@echo ""
	@echo "  - python-upgrade    Update Python version across repo"
	@echo "  - prune-deps        Remove unused dependencies"
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
# .PHONY: prune-deps
# prune-deps: _validate-prune-deps-params _run-prune-deps
#   # Detect and remove unused dependencies
#   # Parameters: SCOPE (optional, defaults to repo-wide)
#   # Example: make prune-deps SCOPE=packages/service-library
#
# .PHONY: test-deps-update
# test-deps-update: _validate-test-deps-update-params _run-test-deps-update
#   # Update test-only dependencies
#   # Parameters: PACKAGE (optional for single pkg or leave empty for all)
#   # Example: make test-deps-update PACKAGE=pytest
#

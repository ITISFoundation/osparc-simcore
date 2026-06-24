#
# Targets for managing the repo-base Python virtual environment.
#
# All uv artifact directories are redirected inside the repo so that both
# interactive and SANDBOXED (e.g. VS Code agent) shells can write to them.
# The sandbox can write to the workspace directory but not to ~/.cache or
# ~/.local/share/uv, so placing UV_CACHE_DIR and UV_PYTHON_INSTALL_DIR
# inside the repo removes that restriction.
#
# Included from the repository root Makefile via:
#   include scripts/makefiles/python-env.mk
#
# Variables expected from the caller (all have sensible defaults):
#   REPO_BASE_DIR   — absolute path to the repository root
#   MAKE_C          — recursive make helper ($(MAKE) --no-print-directory --directory)
#

REPO_BASE_DIR ?= $(CURDIR)

EXPECTED_PYTHON_VERSION := $(shell cat $(REPO_BASE_DIR)/requirements/PYTHON_VERSION)
VENV_DIR                := $(REPO_BASE_DIR)/.venv

# Redirect all uv I/O into the repo so sandbox-restricted shells can write.
# Callers may override these via environment variables before invoking make.
UV_CACHE_DIR          ?= $(REPO_BASE_DIR)/.uv-cache
UV_PYTHON_INSTALL_DIR ?= $(REPO_BASE_DIR)/.uv-python
export UV_CACHE_DIR
export UV_PYTHON_INSTALL_DIR

# ---------------------------------------------------------------------------
# Guards / checks
# ---------------------------------------------------------------------------

.PHONY: test_python_version _check_venv_active

test_python_version: ## Check Python version, throw error if compilation would fail with the installed version
	# Checking python version
	@$(VENV_DIR)/bin/python $(REPO_BASE_DIR)/scripts/test_python_version.py

_check_venv_active:
	# Checking whether virtual environment was activated
	@python3 -c "import sys; assert sys.base_prefix\!=sys.prefix"

# ---------------------------------------------------------------------------
# uv bootstrap
# ---------------------------------------------------------------------------

.check-uv-installed:
	@echo "Checking if 'uv' is installed..."
	@if \! command -v uv >/dev/null 2>&1; then \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	else \
		printf "\033[32m'uv' is installed. Version: \033[0m"; \
		uv --version; \
	fi
	# Upgrading uv — skipped in CI and in non-interactive (sandbox) sessions
	@if [ "${CI}" \!= "true" ] && [ -t 0 ]; then \
		uv self --quiet update; \
	else \
		echo "Skipping 'uv self update' (CI=${CI}, non-interactive or sandbox)"; \
	fi

# ---------------------------------------------------------------------------
# Virtual environment
# ---------------------------------------------------------------------------

# The .venv directory is the Make target; uv creates it.
# Python is installed into UV_PYTHON_INSTALL_DIR (repo-local) when not already present.
$(VENV_DIR): .check-uv-installed
	# Creating virtual environment at $(VENV_DIR) with Python $(EXPECTED_PYTHON_VERSION)
	@uv venv --python $(EXPECTED_PYTHON_VERSION) $@
	@echo "# Python version in venv:" && $@/bin/python --version
	@uv pip list --python $@

# Convenience alias so existing 'make .venv' invocations keep working
.venv: $(VENV_DIR)

# ---------------------------------------------------------------------------
# Developer environment
# ---------------------------------------------------------------------------

.PHONY: devenv devenv-all

devenv: $(VENV_DIR) test_python_version .vscode/settings.json .vscode/launch.json .vscode/mcp.json ## create a development environment (configs, virtual-env, hooks, ...)
	@uv pip --quiet install --python $(VENV_DIR) --requirements $(REPO_BASE_DIR)/requirements/devenv.txt
	# Installing pre-commit hooks in current .git repo
	@$(VENV_DIR)/bin/pre-commit install
	@echo "To activate the venv, execute 'source $(VENV_DIR)/bin/activate'"

devenv-all: devenv ## sets up extra development tools (everything else besides python)
	# Upgrading client compiler
	@$(MAKE_C) services/static-webserver/client upgrade
	# Building tools
	@$(MAKE_C) scripts/json-schema-to-openapi-schema

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

.PHONY: clean-venv clean-hooks

clean-venv: devenv ## Purges .venv into original configuration
	# Cleaning your venv
	@uv pip sync --quiet $(REPO_BASE_DIR)/requirements/devenv.txt
	@uv pip list

clean-hooks: ## Uninstalls git pre-commit hooks
	@-pre-commit uninstall 2> /dev/null || rm .git/hooks/pre-commit

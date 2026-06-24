#
# Targets for managing the repo-base Python virtual environment.
#
# All uv artifacts — the `uv` binary itself, its cache and the managed Python
# toolchain — are redirected inside the repo so that a SANDBOXED shell (e.g. the
# VS Code agent) is fully self-contained and never needs anything from $HOME.
# The sandbox can write to the workspace directory but not to ~/.local/bin,
# ~/.cache or ~/.local/share/uv, so placing UV_INSTALL_DIR, UV_CACHE_DIR and
# UV_PYTHON_INSTALL_DIR inside the repo removes that restriction.
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
UV_INSTALL_DIR        ?= $(REPO_BASE_DIR)/.uv-bin
UV_CACHE_DIR          ?= $(REPO_BASE_DIR)/.uv-cache
UV_PYTHON_INSTALL_DIR ?= $(REPO_BASE_DIR)/.uv-python
export UV_INSTALL_DIR
export UV_CACHE_DIR
export UV_PYTHON_INSTALL_DIR

# Resolve the uv binary by absolute path so no $HOME entry on PATH is ever
# required. It always lives in the repo-local UV_INSTALL_DIR; .check-uv-installed
# creates it there if missing. Keeping it deterministic (never a $HOME copy)
# guarantees the .venv/bin/uv symlink stays valid in a sandbox too.
UV := $(UV_INSTALL_DIR)/uv

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
	@if test ! -x $(UV); then \
		echo "Installing 'uv' into $(UV_INSTALL_DIR) (repo-local) ..."; \
		curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$(UV_INSTALL_DIR)" sh; \
	else \
		printf "\033[32m'uv' is installed. Version: \033[0m"; \
		$(UV) --version; \
	fi
	# Note: no 'uv self update' — the repo-local install (custom UV_INSTALL_DIR)
	# is "unmanaged" and cannot self-update. To upgrade, remove $(UV_INSTALL_DIR)
	# and re-run 'make devenv' to re-bootstrap.

# ---------------------------------------------------------------------------
# Virtual environment
# ---------------------------------------------------------------------------

# The .venv directory is the Make target; uv creates it.
# `.check-uv-installed` is an order-only prerequisite (after `|`): it must run
# before the venv is created, but its always-out-of-date (phony) status must not
# force an existing .venv to be rebuilt.
# Python is installed into UV_PYTHON_INSTALL_DIR (repo-local) when not already present.
$(VENV_DIR): | .check-uv-installed
	# Creating virtual environment at $(VENV_DIR) with Python $(EXPECTED_PYTHON_VERSION)
	@$(UV) venv --python $(EXPECTED_PYTHON_VERSION) $@
	# Exposing repo-local uv inside the venv so that activating it puts uv on
	# PATH. This lets bare 'uv ...' recipes (e.g. service 'make install-dev')
	# resolve the repo-local binary without any external dependency.
	@ln -sf $(UV) $@/bin/uv
	@echo "# Python version in venv:" && $@/bin/python --version
	@$(UV) pip list --python $@

# Convenience alias so existing 'make .venv' invocations keep working
.venv: $(VENV_DIR)

# ---------------------------------------------------------------------------
# Developer environment
# ---------------------------------------------------------------------------

.PHONY: devenv devenv-all

devenv: $(VENV_DIR) test_python_version .vscode/settings.json .vscode/launch.json .vscode/mcp.json ## create a development environment (configs, virtual-env, hooks, ...)
	# Ensuring repo-local uv is reachable on PATH once the venv is activated
	# (idempotent; also covers venvs created before this symlink existed).
	@ln -sf $(UV) $(VENV_DIR)/bin/uv
	@$(UV) pip --quiet install --python $(VENV_DIR) --requirements $(REPO_BASE_DIR)/requirements/devenv.txt
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
	@$(UV) pip sync --quiet $(REPO_BASE_DIR)/requirements/devenv.txt
	@$(UV) pip list

clean-hooks: ## Uninstalls git pre-commit hooks
	@-pre-commit uninstall 2> /dev/null || rm .git/hooks/pre-commit

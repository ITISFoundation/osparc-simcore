#
# Targets to pip-compile requirements
#
include ../../../requirements/base.Makefile

VENV_DIR ?= $(realpath $(REPO_BASE_DIR)/.venv)


.PHONY: install
install: $(VENV_DIR) requirements.txt ## installs dependencies
	# installing requirements
	@uv pip install -r requirements.txt

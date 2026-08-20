#
# Shared virtual-env install targets for packages and services.
#
# LIBRARY (.mk): include-only, not a directly-invoked entry point.
# Single source of truth for `install-dev|install-prod|install-ci`; replaces the
# copy that used to be duplicated in every package/service Makefile.
# SEE scripts/makefiles/README.md for conventions.
#

.PHONY: install-dev install-prod install-ci

# CI-CONTRACT: install-ci is invoked by ci/github/**/*.bash
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# Installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt

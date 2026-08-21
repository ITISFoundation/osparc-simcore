#
# Targets for DEVELOPMENT of common Library
#
include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/package.mk

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	@uv pip sync requirements/$(subst install-,,$@).txt

install-dev: _check_venv_active ## install app in development mode (editable) and compile locale .mo files
	# installing in dev mode
	@uv pip sync requirements/dev.txt
	# compiling locale .po -> .mo in-place (editable install bypasses build_py hook)
	@python -c "import polib; from pathlib import Path; [polib.pofile(str(p)).save_as_mofile(str(p.with_suffix('.mo'))) for p in Path('src/common_library/locale').glob('*/LC_MESSAGES/messages.po')]"


PYTEST_JUNIT_ARGS :=

.PHONY: tests tests-ci
tests: test-dev-unit ## runs unit tests

# CI-CONTRACT: tests-ci is invoked by ci/github/**/*.bash
tests-ci: test-ci-unit ## runs unit tests in CI mode [CI]

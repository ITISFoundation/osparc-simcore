#
# Python code-style, linting and static type-checking targets.
#
# LIBRARY (.mk): include-only, not a directly-invoked entry point.
# Requires globals.mk (REPO_BASE_DIR) to be included first.
# SEE scripts/makefiles/README.md for conventions.
#

# ---------------------------------------------------------------------------
# MAIN LINTING TARGETS (alphabetically ordered)
# ---------------------------------------------------------------------------

.PHONY: codestyle
codestyle codestyle-ci: ## enforces codestyle (isort & black) finally runs pylint & mypy
	@$(SCRIPTS_DIR)/codestyle.bash $(if $(findstring -ci,$@),ci,development) $(shell basename "${SRC_DIR}")


.PHONY: mypy
mypy: $(REPO_BASE_DIR)/mypy.ini ## runs mypy python static type-checker on this services's code. Use AFTER make install-*
	@mypy \
	--config-file=$(REPO_BASE_DIR)/mypy.ini \
	--show-error-context \
	--show-traceback \
	$(CURDIR)/src


.PHONY: mypy-debug
mypy-debug: $(REPO_BASE_DIR)/mypy.ini  ## runs mypy with profiling and reporting enabled
	$(eval MYPY_REPORT_DIR := $(CURDIR)/.mypy-report.ignore)
	@rm -rf $(MYPY_REPORT_DIR)
	@mkdir -p $(MYPY_REPORT_DIR)
	@mypy \
	  --config-file=$(REPO_BASE_DIR)/mypy.ini \
	  --show-error-context \
	  --show-traceback \
	  --verbose \
	  --linecount-report $(MYPY_REPORT_DIR) \
	  --any-exprs-report $(MYPY_REPORT_DIR) \
	  $(CURDIR)/src \
	  2>&1 | tee $(MYPY_REPORT_DIR)/mypy.logs


.PHONY: pylint
pylint: $(REPO_BASE_DIR)/.pylintrc ## runs pylint (python linter) on src and tests folders
	@pylint --rcfile="$(REPO_BASE_DIR)/.pylintrc" -v $(CURDIR)/src $(CURDIR)/tests


.PHONY: ruff
ruff: $(REPO_BASE_DIR)/.ruff.toml ## runs ruff (python fast linter) on src and tests folders
	@ruff check \
		--config=$(REPO_BASE_DIR)/.ruff.toml \
		--respect-gitignore \
		$(CURDIR)/src \
		$(CURDIR)/tests


# ---------------------------------------------------------------------------
# DEVELOPER-ONLY CONVENIENCE TARGETS (alphabetically ordered)
# REVIEW: no known CI or docs callers. Safe to keep or drop as a batch.
# ---------------------------------------------------------------------------

.PHONY: codeformat
codeformat: ## runs all code formatters. Use AFTER make install-*
	@$(eval PYFILES=$(shell find $(CURDIR) -type f -name '*.py'))
	@pre-commit run pyupgrade --files $(PYFILES)
	@pre-commit run pycln --files $(PYFILES)
	@pre-commit run isort --files $(PYFILES)
	@pre-commit run black --files $(PYFILES)


.PHONY: doc-uml
doc-uml: $(IGNORE_DIR) ## Create UML diagrams for classes and modules in current package. e.g. (export DOC_UML_PATH_SUFFIX="services*"; export DOC_UML_CLASS=models_library.api_schemas_catalog.services.ServiceGet; make doc-uml)
	@pyreverse \
		--verbose \
		--output=svg \
		--output-directory=$(IGNORE_DIR) \
		--project=$(if ${PACKAGE_NAME},${PACKAGE_NAME},${SERVICE_NAME})${DOC_UML_PATH_SUFFIX} \
		$(if ${DOC_UML_CLASS},--class=${DOC_UML_CLASS},) \
		${SRC_DIR}$(if ${DOC_UML_PATH_SUFFIX},/${DOC_UML_PATH_SUFFIX},)
	@echo Outputs in $(realpath $(IGNORE_DIR))


.PHONY: pyupgrade
pyupgrade: ## upgrades python syntax for newer versions of the language (SEE https://github.com/asottile/pyupgrade)
	@pre-commit run pyupgrade --files $(shell find $(CURDIR) -type f -name '*.py')

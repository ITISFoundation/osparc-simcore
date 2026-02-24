#
# Targets for DEVELOPMENT of models Library
#
# All standard targets (install-dev/prod/ci, tests/tests-ci) are defined in
# ../../scripts/common-package.Makefile and included below.
#

include ../../scripts/common.Makefile
include ../../scripts/common-package.Makefile


#
# Auto-generation targets (specific to models-library)
#

DOCKER_API_VERSION ?= 1.44
.PHONY: docker_rest_api.py
docker_rest_api.py: ## auto-generates pydantic models for Docker REST API models
	# auto-generates $@ from $<
	@$(SCRIPTS_DIR)/openapi-pydantic-models-generator.bash \
			--url https://docs.docker.com/reference/api/engine/version/v$(DOCKER_API_VERSION).yaml \
			--output $@

	# formats
	@ruff format $@
	# copy output to src/models_library/generated_models...
	@mkdir --parents src/models_library/generated_models
	@mv $@ src/models_library/generated_models/$@
	@touch src/models_library/generated_models/__init__.py
	# done



#
# erdantic's recipes
#     Entity Relationship Diagrams (ERD) for pydantic models
#
#  - NOTE: these tools require graphviz!
#  - SEE https://erdantic.drivendata.org/stable/
#
.PHONY: _erdantic
_erdantic: _check_venv_active
	# ensures erdantic installed
	@python3 -c "import erdantic" 2>/dev/null || uv pip install erdantic

erd-Project.svg: _erdantic
	erdantic models_library.projects.Project \
		--out $@

erd-ProjectAtDB.svg: _erdantic
	erdantic models_library.projects.ProjectAtDB \
		--out $@

erd-Node.svg: _erdantic
	erdantic models_library.projects_nodes.Node \
		--out $@

erd-ServiceInput.svg: _erdantic
	erdantic models_library.services.ServiceInput \
		--out $@


#
# Test data
#

DOWNLOADED_TEST_DATA_DIR = "$(CURDIR)/tests/data/.downloaded-ignore"

.PHONY: _httpx
_ensure_httpx: _check_venv_active
	# ensures requirements installed
	@python3 -c "import httpx" 2>/dev/null || uv pip install httpx

PHONY: tests-data
tests-data: $(DOT_ENV_FILE) _ensure_httpx ## downloads tests data from registry defined in .env (time-intensive!)
	# Downloading all metadata files ...
	@set -o allexport; \
	source $<; \
	set +o allexport; \
	python3 "$(PACKAGES_DIR)/pytest-simcore/src/pytest_simcore/helpers/docker_registry.py" $(DOWNLOADED_TEST_DATA_DIR)
	@echo "Run now 'pytest -vv -m diagnostics tests'"

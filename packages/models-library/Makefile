#
# Targets for DEVELOPMENT of models Library
#
include ../../scripts/common.Makefile
include ../../scripts/common-package.Makefile

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


.PHONY: tests
tests: ## runs unit tests
	# running unit tests
	@pytest -vv --color=yes --exitfirst --failed-first --durations=10 \
	--cov-config=../../.coveragerc --cov=models_library --cov-report=term-missing \
	--asyncio-mode=auto \
	--pdb $(CURDIR)/tests


.PHONY: project-jsonschema.ignore.json
project-jsonschema.ignore.json: ## creates project-v0.0.1.json for DEV purposes
	python3 -c "from models_library.projects import Project; print(Project.schema_json(indent=2))" > $@

.PHONY: service-jsonschema.ignore.json
node-meta-jsonschema.ignore.json: ## creates node-meta-v0.0.1.json for DEV purposes
	python3 -c "from models_library.services import ServiceDockerData as cls; print(cls.schema_json(indent=2))" > $@

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
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests



compose-spec.json:
	# Downloading schema from https://github.com/compose-spec/compose-spec
	wget https://raw.githubusercontent.com/compose-spec/compose-spec/master/schema/$@

compose_spec_model.py: compose-spec.json ## auto-generates pydantic model for compose-specification
	# auto-generates $@ from $<
	datamodel-codegen  --input $< --input-file-type jsonschema --output $@

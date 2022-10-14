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


.PHONY: tests test-ci-unit
tests: ## runs unit tests
	# running unit tests
	@pytest \
		--color=yes \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov=service_integration \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--pdb \
		-vv \
		$(CURDIR)/tests

test-ci-unit: ## runs unit tests [ci-mode]
	# running unit tests
	@pytest \
		--color=yes \
		--cov-append \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=service_integration \
		--durations=10 \
		--log-date-format="%Y-%m-%d %H:%M:%S" \
    --log-format="%(asctime)s %(levelname)s %(message)s" \
    --verbose \
    -m "not heavy_load" \
		$(CURDIR)/tests


# Auto-generation of compose-spec model

compose-spec.json:
	# Downloading schema from https://github.com/compose-spec/compose-spec
	wget https://raw.githubusercontent.com/compose-spec/compose-spec/master/schema/$@
	echo $(shell cat $@ | jq '."$$schema"')


.PHONY:
_compose_spec_model.py: ## auto-generates pydantic model for compose-specification
	# auto-generates $@ from $<
	datamodel-codegen  \
		--url https://raw.githubusercontent.com/compose-spec/compose-spec/master/schema/compose-spec.json \
		--input-file-type jsonschema \
		--snake-case-field \
		--use-schema-description  \
		--aliases ALIASES.json \
		--output $@
	# formats and moves
	black $@
	mv $@ src/service_integration/$@

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


.PHONY: tests tests-ci
tests: ## runs unit tests
	# running unit tests
	@pytest \
		--color=yes \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov=invitations_maker \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--pdb \
		-vv \
		$(CURDIR)/tests

tests-ci: ## runs unit tests [ci-mode]
	# running unit tests
	@pytest \
		--color=yes \
		--cov-append \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=invitations_maker \
		--durations=10 \
		--log-date-format="%Y-%m-%d %H:%M:%S" \
    --log-format="%(asctime)s %(levelname)s %(message)s" \
    --verbose \
    -m "not heavy_load" \
		$(CURDIR)/tests




#
# Docker image (executable)
#

.PHONY: build build-nc
build build-nc: ## [docker] builds docker image of executable w/ or w/o cache
	# Building docker image for ${PACKAGE_NAME} ...
	@$(MAKE_C) ${REPO_BASE_DIR} $@ target=${PACKAGE_NAME}
	# Test run
	docker run local/${PACKAGE_NAME}:production --version

.PHONY: inspect
inspect: ## [docker] inspects container
	docker image inspect \
		local/${PACKAGE_NAME}:production | jq '.[0] | .RepoTags, .Config.Labels, .Architecture'


_src_dir = $(if $(target),$(target),$(PWD))

.PHONY: shell
shell: ## [docker] opens shell in container
	docker run \
		-it \
		--volume="/etc/group:/etc/group:ro" \
		--volume="/etc/passwd:/etc/passwd:ro" \
		--user="$(shell id --user "$(USER)")":scu \
		--entrypoint bash \
		--volume "$(_src_dir)":/src \
		--workdir=/src \
		local/${PACKAGE_NAME}:production

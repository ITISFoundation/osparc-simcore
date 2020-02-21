#
# TODO: under development
#
.DEFAULT_GOAL := help

REPO_BASE_DIR  = $(abspath $(CURDIR)/../../)

.PHONY: devenv
devenv: ## build development environment (using main services/docker-compose-build.yml)
	@$(MAKE) --directory ${REPO_BASE_DIR} $@


.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE) --directory requirements all


.check-venv-active:
	# checking whether virtual environment was activated
	@python3 -c "import sys; assert sys.base_prefix!=sys.prefix"

.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: requirements .check-venv-active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


.PHONY: tests
tests: ## runs unit tests
	# running unit tests
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests


.PHONY: version-patch version-minor
version-patch version-minor version-major: ## commits version as patch (bug fixes not affecting the API), minor/minor (backwards-compatible/INcompatible API addition or changes)
	# upgrades as $(subst version-,,$@) version, commits and tags
	@bump2version --verbose --list $(subst version-,,$@)


.PHONY: info
info: ## displays
	# installed
	@pip list
	# version
	@cat setup.py | grep version=


.PHONY: setup-commit
setup-commit: install-dev up-pg ## sets up a database to create a new commit into migration history
	# discovering
	sc-pg --help
	sc-pg discover -u test -p test -d test
	# upgrade
	sc-pg upgrade
	# some info
	sc-pg info
	@echo "To add new commit, sc-pg review -m "Some message" "


_docker_compose_config := tests/docker-compose.yml

.PHONY: up-pg down-pg

up-pg: ## starts pg server
	docker-compose -f $(_docker_compose_config) up -d

down-pg: ## stops pg server
	docker-compose -f $(_docker_compose_config) down


.PHONY: autoformat
autoformat: ## runs black python formatter on this service's code [https://black.readthedocs.io/en/stable/]
	# auto formatting with black
	@python3 -m black --verbose \
		--exclude "/(\.eggs|\.git|\.hg|\.mypy_cache|\.nox|\.tox|\.venv|\.svn|_build|buck-out|build|dist|migration)/" \
		$(CURDIR)


.PHONY: clean
clean: down ## cleans all unversioned files in project and temp files create by this makefile
	# Cleaning unversioned
	@git clean -ndxf
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo -n "$(shell whoami), are you REALLY sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@git clean -dxf


.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

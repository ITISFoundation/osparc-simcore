#
# Targets for DEVELOPMENT of postgres-database
#
include ../../scripts/common.Makefile

REPO_BASE_DIR  = $(abspath $(CURDIR)/../../)

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE) --directory requirements all


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: requirements _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


.PHONY: tests
tests: ## runs unit tests
	# running unit tests
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests


.PHONY: setup-commit
setup-commit: install-dev up-pg ## sets up a database to create a new commit into migration history
	# discovering
	sc-pg --help
	sc-pg discover -u test -p test -d test
	# upgrade
	sc-pg upgrade
	# some info
	sc-pg info
	@echo "To add new commit, sc-pg review -m \"Some message\" "


.PHONY: migrate
DOT_ENV_FILE = $(abspath $(REPO_BASE_DIR)/.env)

migrate: $(DOT_ENV_FILE) ## basic migration update (use ONLY for development purposes)
	# Discovering postpgres server
	@export $(shell grep -v '^#' $< | xargs -0); sc-pg discover
	# Upgraded to head
	@sc-pg upgrade
	@sc-pg clean




.PHONY: up-pg down-pg
DOCKER_COMPOSE_CONFIG := tests/docker-compose.yml

up-pg: $(DOCKER_COMPOSE_CONFIG) ## starts pg server
	docker-compose -f $< up -d

down-pg: $(DOCKER_COMPOSE_CONFIG) ## stops pg server
	docker-compose -f $< down

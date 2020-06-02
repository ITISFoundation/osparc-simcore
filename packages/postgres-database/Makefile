#
# Targets for DEVELOPMENT of postgres-database
#
include ../../scripts/common.Makefile


.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: requirements _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


.PHONY: tests
tests: ## runs unit tests
	# running unit tests
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests


.PHONY: import-db
import-db: scripts/copy_database_volume.sh guard-SOURCE_HOST guard-SOURCE_DATA_VOLUME guard-TARGET_DATA_VOLUME ## copy volume $(SOURCE_DATA_VOLUME) from $(SOURCE_HOST) into local $(TARGET_DATA_VOLUME)
	./scripts/copy_database_volume.sh

guard-%:
	@ if [ "${${*}}" = "" ]; then \
		echo "Environment variable $* not set"; \
		exit 1; \
	fi

.PHONY: setup-prod
export POSTGRES_DATA_VOLUME = $(TARGET_DATA_VOLUME)
setup-prod: install-dev up-prod  ## sets up a database using an external postgres volume to test migration
	# discovering
	sc-pg --help
	@echo "To test migration, sc-pg discover -u USER -p PASSWORD, then sc-pg upgrade"

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
	# adminer: http://127.0.0.1:18080/?pgsql=postgres&username=test&db=test&ns=public


.PHONY: migrate
DOT_ENV_FILE = $(abspath $(REPO_BASE_DIR)/.env)

migrate: $(DOT_ENV_FILE) ## basic migration update (use ONLY for development purposes)
	# Discovering postpgres server
	@export $(shell grep -v '^#' $< | xargs -0); sc-pg discover
	# Upgraded to head
	@sc-pg upgrade
	@sc-pg clean




.PHONY: up-pg down-pg up-prod down-prod
docker-compose-configs = $(wildcard tests/docker-compose*.yml)
up-pg up-prod: $(docker-compose-configs) ## starts pg server
	docker-compose -f tests/docker-compose.yml $(if $(findstring -prod,$@),-f tests/docker-compose.prod.yml,) up -d

down-pg down-prod: $(docker-compose-configs) ## stops pg server
	docker-compose -f tests/docker-compose.yml  $(if $(findstring -prod,$@),-f tests/docker-compose.prod.yml,) down

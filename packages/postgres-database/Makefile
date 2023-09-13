#
# Targets for DEVELOPMENT of postgres-database
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
		--asyncio-mode=auto \
		--color=yes \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov=simcore_postgres_database \
		--durations=10 \
		--exitfirst \
		--failed-first \
		--pdb \
		-vv \
		$(CURDIR)/tests

tests-ci: ## runs unit tests [ci-mode]
	# running unit tests
	@pytest \
		--asyncio-mode=auto \
		--color=yes \
		--cov-append \
		--cov-config=../../.coveragerc \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov=simcore_postgres_database \
		--durations=10 \
		--log-date-format="%Y-%m-%d %H:%M:%S" \
    --log-format="%(asctime)s %(levelname)s %(message)s" \
    --verbose \
    -m "not heavy_load" \
		$(CURDIR)/tests


.PHONY: import-db
#guard-SOURCE_HOST guard-SOURCE_DATA_VOLUME guard-TARGET_DATA_VOLUME
import-db-from-docker-volume import-db-from-folder: scripts/copy_database_volume.sh  ## copy postgresql data from remote $host from $host_volume or $host_folder to a local $local_volume docker volume
	@:$(if $(findstring -from-folder,$@),\
	$(call check_defined, host host_folder local_volume, please define this variable when calling $@), \
	$(call check_defined, host host_volume local_volume, please define this variable when calling $@))
	./scripts/copy_database_volume.sh \
		--host $(host) \
		$(if $(findstring -from-folder, $@),--folder $(host_folder),--volume $(host_volume)) \
		--target $(local_volume)

# Check that given variables are set and all have non-empty values,
# die with an error otherwise.
#
# Params:
#   1. Variable name(s) to test.
#   2. (optional) Error message to print.
guard-%:
	@ if [ "${${*}}" = "" ]; then \
		echo "Environment variable $* not set"; \
		exit 1; \
	fi

# Check that given variables are set and all have non-empty values,
# die with an error otherwise.
#
# Params:
#   1. Variable name(s) to test.
#   2. (optional) Error message to print.
check_defined = \
    $(strip $(foreach 1,$1, \
        $(call __check_defined,$1,$(strip $(value 2)))))
__check_defined = \
    $(if $(value $1),, \
      $(error Undefined $1$(if $2, ($2))))

.PHONY: setup-prod
setup-prod: guard-POSTGRES_DATA_VOLUME install-dev up-prod ## sets up a database using an external postgres volume defined as $POSTGRES_DATA_VOLUME to test migration
	# discovering
	sc-pg --help
	@echo "To test migration, sc-pg discover -u USER -p PASSWORD, then sc-pg upgrade"
	# adminer: http://127.0.0.1:18080/?pgsql=postgres&ns=public

.PHONY: setup-commit
setup-commit: install-dev up-pg ## sets up a database to create a new commit into migration history
	sleep 2
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
	docker compose -f tests/docker-compose.yml $(if $(findstring -prod,$@),-f tests/docker-compose.prod.yml,) up -d

down-pg down-prod: $(docker-compose-configs) ## stops pg server
	docker compose -f tests/docker-compose.yml  $(if $(findstring -prod,$@),-f tests/docker-compose.prod.yml,) down



.PHONY: auto-doc
auto-doc: ## Creates entity relationship diagram (ERD) defined under ``simcore_postgres_database.models``
	$(MAKE) --directory=scripts/erd run

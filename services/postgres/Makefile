.DEFAULT_GOAL := help

REPO_BASE_DIR  = $(abspath $(CURDIR)/../../../)
VENV_DIR ?= $(abspath $(REPO_BASE_DIR)/.venv)

APP_NAME     := postgres

# this is a way to get a valid git repo/git branch
LOCAL_BRANCH = $(shell git name-rev --name-only HEAD)
TRACKING_BRANCH = $(shell git config branch.$(LOCAL_BRANCH).merge)
TRACKING_REMOTE = $(shell git config branch.$(LOCAL_BRANCH).remote)
REMOTE_URL = $(shell git config remote.$(TRACKING_REMOTE).url)

# these variable may be overriden
GIT_REPOSITORY ?= $(subst git@github.com:,https://github.com/,$(REMOTE_URL))
GIT_BRANCH ?= $(LOCAL_BRANCH)

MIGRATER_NAME = maintenance_postgres_migration
MIGRATER_TAG_NAME = local/$(MIGRATER_NAME):latest
SIMCORE_NETWORK ?= simcore_default


.PHONY: build
build: ## build postgres migration image
	# use $(GIT_REPOSITORY) $(GIT_BRANCH)
	@docker build --file Dockerfile \
				  --tag $(MIGRATER_TAG_NAME) \
				  --build-arg GIT_REPOSITORY=$(GIT_REPOSITORY) \
				  --build-arg GIT_BRANCH=$(GIT_BRANCH) \
				  .

.PHONY: migrate-db
migrate-db: ## migrate the postgres database
	@docker service create --restart-condition=on-failure \
						   --network $(SIMCORE_NETWORK) \
						   --name $(MIGRATER_NAME) \
						   --replicas 1 \
						   --init \
						   --detach \
						   $(MIGRATER_TAG_NAME)

.PHONY: down
down: ## stop migration service
	@docker service rm $(MIGRATER_NAME)

.PHONY: clean
clean: ## cleans all unversioned files in project and temp files create by this makefile
	# Cleaning unversioned
	@git clean -ndxf -e .vscode/
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo -n "$(shell whoami), are you REALLY sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@git clean -dxf -e .vscode/


.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '${APP_NAME}':"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

.DEFAULT_GOAL := help

REPO_BASE_DIR  = $(abspath $(CURDIR)/../../../)
VENV_DIR ?= $(abspath $(REPO_BASE_DIR)/.venv)

APP_NAME     := tool_$(notdir $(abspath $(CURDIR)/../))

# this is a way to get a valid git repo/git branch
LOCAL_BRANCH = $(shell git name-rev --name-only HEAD)
TRACKING_BRANCH = $(shell git config branch.$(LOCAL_BRANCH).merge)
TRACKING_REMOTE = $(shell git config branch.$(LOCAL_BRANCH).remote)
REMOTE_URL = $(shell git config remote.$(TRACKING_REMOTE).url)

# these variable may be overriden
GIT_REPOSITORY ?= $(subst git@github.com:,https://github.com/,$(REMOTE_URL))
GIT_BRANCH ?= $(LOCAL_BRANCH)

MIGRATER_TAG_NAME = local/$(APP_NAME):latest
SWARM_STACK_NAME ?= simcore
SIMCORE_NETWORK ?= $(SWARM_STACK_NAME)_default


.PHONY: build
build: ## build postgres migration image
	# use $(GIT_REPOSITORY) $(GIT_BRANCH)
	@docker build --file Dockerfile \
				  --tag $(MIGRATER_TAG_NAME) \
				  --build-arg GIT_REPOSITORY=$(GIT_REPOSITORY) \
				  --build-arg GIT_BRANCH=$(GIT_BRANCH) \
				  .

.PHONY: upgrade
upgrade: ## migrate the postgres database
	@docker service create --restart-condition=on-failure \
						   --network $(SIMCORE_NETWORK) \
						   --name $(APP_NAME) \
						   --replicas 1 \
						   --init \
						   --detach \
						   $(MIGRATER_TAG_NAME)
	@sleep 2
	@TASK_ID=$$(docker service ps --format="{{.ID}}" $(APP_NAME));\
	TASK_STATE=$$(docker inspect --format="{{.Status.State}}" $${TASK_ID});\
	while [ "$${TASK_STATE}" != "complete" ] && [ "$${TASK_STATE}" != "failed" ] && [ "$${TASK_STATE}" != "rejected" ]; do\
		echo "waiting for migration to finish..., (current state: $${TASK_STATE})"; \
		sleep 1; \
		TASK_STATE=$$(docker inspect --format="{{.Status.State}}" $${TASK_ID});\
	done
	@docker service rm $(APP_NAME)


.PHONY: down
down: ## stop migration service
	@docker service rm $(APP_NAME)

.PHONY: clean
clean: ## clean all created images
	-@docker image rm -f $(shell docker images */$(APP_NAME):* -q)

.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '${APP_NAME}':"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

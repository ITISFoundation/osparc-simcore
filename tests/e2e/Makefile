.DEFAULT_GOAL := help

# Operating system
ifeq ($(filter Windows_NT,$(OS)),)
IS_WSL  := $(if $(findstring Microsoft,$(shell uname -a)),WSL,)
IS_OSX  := $(filter Darwin,$(shell uname -a))
IS_LINUX:= $(if $(or $(IS_WSL),$(IS_OSX)),,$(filter Linux,$(shell uname -a)))
endif

IS_WIN  := $(strip $(if $(or $(IS_LINUX),$(IS_OSX),$(IS_WSL)),,$(OS)))
$(if $(IS_WIN),$(error Windows is not supported in all recipes. Use WSL instead. Follow instructions in README.md),)

SHELL := /bin/bash

.PHONY: help
help: ## help on rule's targets
ifeq ($(IS_WIN),)
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
else
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
endif


.PHONY: install
install: ## install testing framework
	# install puppeteer
	@npm install
	@pip install -r requirements/requirements.txt
	# installing postgres-db
	@pushd "$(abspath $(CURDIR)/../../packages/postgres-database)"; pip install -r requirements/prod.txt; popd


registry-up: ## deploys the insecure docker registry in the simcore network
	docker stack deploy -c docker-compose.yml registry

registry-down: ## bring the docker registry down
	docker stack rm registry


.PHONY: wait-for-services
wait-for-services: ## wait for simcore services to be up
	@python utils/wait_for_services.py

.PHONY: transfer-images-to-registry
transfer-images-to-registry: ## transfer images to registry
	@docker pull itisfoundation/sleeper:1.0.0
	@docker tag itisfoundation/sleeper:1.0.0 registry:5000/simcore/services/comp/itis/sleeper:1.0.0
	@docker push registry:5000/simcore/services/comp/itis/sleeper:1.0.0

	# @docker pull itisfoundation/jupyter-base-notebook:2.13.0
	# @docker tag itisfoundation/jupyter-base-notebook:2.13.0 registry:5000/simcore/services/dynamic/jupyter-base-notebook:2.13.0
	# @docker push registry:5000/simcore/services/dynamic/jupyter-base-notebook:2.13.0
	# completed transfer of images
	curl -s registry:5000/v2/_catalog | jq '.repositories'

PUBLISHED_PORT = $(shell docker inspect $(shell docker service ls --format "{{ .Name }}" | grep postgres) --format "{{(index .Endpoint.Ports 0).PublishedPort}}")
.PHONY: inject-templates-in-db
inject-templates-in-db: ## inject project templates
	# Injecting fixture tables in database via port $(PUBLISHED_PORT)
	PGPASSWORD=adminadmin psql \
		--host 127.0.0.1 \
		--port $(PUBLISHED_PORT) \
		--user scu \
		--dbname simcoredb \
		--command "\copy projects from 'tutorials/sleepers_project_template_sql.csv' csv header;";

.PHONY: test
test: ## test the platform
	# tests
	npm test
	# tests whether tutorial run
	npm run tutorials http://127.0.0.1:9081

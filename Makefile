# osparc-simcore general makefile
#
# NOTES:
# 	- GNU make version 4.2 recommended
# 	- Use 'make -n *' to dry-run during debugging
# 	- In windows, only WSL is supported
#
# by sanderegg, pcrespov
#
.DEFAULT_GOAL := help

SHELL := /bin/bash

MAKE_C := $(MAKE) --no-print-directory --directory

# Operating system
ifeq ($(filter Windows_NT,$(OS)),)
IS_WSL  := $(if $(findstring Microsoft,$(shell uname -a)),WSL,)
IS_WSL2 := $(if $(findstring -microsoft-,$(shell uname -a)),WSL2,)
IS_OSX  := $(filter Darwin,$(shell uname -a))
IS_LINUX:= $(if $(or $(IS_WSL),$(IS_OSX)),,$(filter Linux,$(shell uname -a)))
endif

IS_WIN  := $(strip $(if $(or $(IS_LINUX),$(IS_OSX),$(IS_WSL)),,$(OS)))
$(if $(IS_WIN),$(error Windows is not supported in all recipes. Use WSL instead. Follow instructions in README.md),)

# VARIABLES ----------------------------------------------
# NOTE: Name given to any of the services that must be build, regardless
# whether they are part of the simcore stack or not. This list can be obtained from
#
# cat services/docker-compose-build.yml | yq ".services | keys | sort"
#
SERVICES_NAMES_TO_BUILD := \
  agent \
  api-server \
  autoscaling \
  catalog \
	clusters-keeper \
  dask-sidecar \
  datcore-adapter \
  director \
  director-v2 \
  dynamic-sidecar \
	invitations \
  migration \
	osparc-gateway-server \
	payments \
	resource-usage-tracker \
  service-integration \
  static-webserver \
  storage \
  webserver

CLIENT_WEB_OUTPUT       := $(CURDIR)/services/static-webserver/client/source-output

# version control
export VCS_URL          := $(shell git config --get remote.origin.url)
export VCS_REF          := $(shell git rev-parse HEAD)
export VCS_REF_CLIENT   := $(shell git log --pretty=tformat:"%h" -n1 services/static-webserver/client)
export VCS_STATUS_CLIENT:= $(if $(shell git status -s),'modified/untracked','clean')
export BUILD_DATE       := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

# api-versions
export AGENT_API_VERSION := $(shell cat $(CURDIR)/services/api-server/VERSION)
export API_SERVER_API_VERSION := $(shell cat $(CURDIR)/services/api-server/VERSION)
export AUTOSCALING_API_VERSION := $(shell cat $(CURDIR)/services/autoscaling/VERSION)
export CATALOG_API_VERSION    := $(shell cat $(CURDIR)/services/catalog/VERSION)
export DIRECTOR_API_VERSION   := $(shell cat $(CURDIR)/services/director/VERSION)
export DIRECTOR_V2_API_VERSION:= $(shell cat $(CURDIR)/services/director-v2/VERSION)
export STORAGE_API_VERSION    := $(shell cat $(CURDIR)/services/storage/VERSION)
export INVITATIONS_API_VERSION  := $(shell cat $(CURDIR)/services/invitations/VERSION)
export PAYMENTS_API_VERSION  := $(shell cat $(CURDIR)/services/payments/VERSION)
export DATCORE_ADAPTER_API_VERSION    := $(shell cat $(CURDIR)/services/datcore-adapter/VERSION)
export WEBSERVER_API_VERSION  := $(shell cat $(CURDIR)/services/web/server/VERSION)


# swarm stacks
export SWARM_STACK_NAME ?= master-simcore
export SWARM_STACK_NAME_NO_HYPHEN = $(subst -,_,$(SWARM_STACK_NAME))

# version tags
export DOCKER_IMAGE_TAG ?= latest
export DOCKER_REGISTRY  ?= itisfoundation

# NOTE: this is only for WSL1 as /etc/hostname is not accessible there
ifeq ($(IS_WSL),WSL)
ETC_HOSTNAME = $(CURDIR)/.fake_hostname_file
export ETC_HOSTNAME
host := $(shell echo $$(hostname) > $(ETC_HOSTNAME))
endif

get_my_ip := $(shell hostname --all-ip-addresses | cut --delimiter=" " --fields=1)

# NOTE: this is only for WSL2 as the WSL2 subsystem IP is changing on each reboot
ifeq ($(IS_WSL2),WSL2)
S3_ENDPOINT := $(get_my_ip):9001
export S3_ENDPOINT
endif

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
# exit with an error otherwise.
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


.PHONY: help

help: ## help on rule's targets
ifeq ($(IS_WIN),)
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
else
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
endif



## DOCKER BUILD -------------------------------
#
# - all builds are inmediatly tagged as 'local/{service}:${BUILD_TARGET}' where BUILD_TARGET='development', 'production', 'cache'
# - only production and cache images are released (i.e. tagged pushed into registry)
#
SWARM_HOSTS = $(shell docker node ls --format="{{.Hostname}}" 2>$(if $(IS_WIN),NUL,/dev/null))

.PHONY: build build-nc rebuild build-devel build-devel-nc

# docker buildx cache location
DOCKER_BUILDX_CACHE_FROM ?= /tmp/.buildx-cache
DOCKER_BUILDX_CACHE_TO ?= /tmp/.buildx-cache
DOCKER_TARGET_PLATFORMS ?= linux/amd64
comma := ,

define _docker_compose_build
export BUILD_TARGET=$(if $(findstring -devel,$@),development,production) &&\
pushd services &&\
$(foreach service, $(SERVICES_NAMES_TO_BUILD),\
	$(if $(push),\
		export $(subst -,_,$(shell echo $(service) | tr a-z A-Z))_VERSION=$(shell cat services/$(service)/VERSION);\
	,) \
)\
docker buildx bake \
	$(if $(findstring -devel,$@),,\
	--set *.platform=$(DOCKER_TARGET_PLATFORMS) \
	)\
	$(if $(findstring $(comma),$(DOCKER_TARGET_PLATFORMS)),,\
		$(if $(local-dest),\
			$(foreach service, $(SERVICES_NAMES_TO_BUILD),\
				--set $(service).output="type=docker$(comma)dest=$(local-dest)/$(service).tar") \
			,--load\
		)\
	)\
	$(if $(push),--push,) \
	$(if $(push),--file docker-bake.hcl,) --file docker-compose-build.yml $(if $(target),$(target),) \
	$(if $(findstring -nc,$@),--no-cache,\
		$(foreach service, $(SERVICES_NAMES_TO_BUILD),\
			--set $(service).cache-to=type=gha$(comma)mode=max$(comma)scope=$(service) \
			--set $(service).cache-from=type=gha$(comma)scope=$(service)) \
	) &&\
popd;
endef

rebuild: build-nc # alias
build build-nc: .env ## Builds production images and tags them as 'local/{service-name}:production'. For single target e.g. 'make target=webserver build'. To export to a folder: `make local-dest=/tmp/build`
	# Building service$(if $(target),,s) $(target)
	@$(_docker_compose_build)
	# List production images
	@docker images --filter="reference=local/*:production"

load-images: guard-local-src ## loads images from local-src
	# loading from images from $(local-src)...
	@$(foreach service, $(SERVICES_NAMES_TO_BUILD),\
		docker load --input $(local-src)/$(service).tar; \
	)
	# all images loaded
	@docker images

build-devel build-devel-nc: .env ## Builds development images and tags them as 'local/{service-name}:development'. For single target e.g. 'make target=webserver build-devel'
ifeq ($(target),)
	# Building services
	@$(_docker_compose_build)
else
ifeq ($(findstring static-webserver,$(target)),static-webserver)
	# Compiling front-end
	$(MAKE_C) services/static-webserver/client touch compile-dev
endif
	# Building service $(target)
	@$(_docker_compose_build)
endif
	# List development images
	@docker images --filter="reference=local/*:development"


$(CLIENT_WEB_OUTPUT):
	# Ensures source-output folder always exists to avoid issues when mounting webclient->static-webserver dockers. Supports PowerShell
	-mkdir $(if $(IS_WIN),,-p) $(CLIENT_WEB_OUTPUT)


.PHONY: shell
shell:
	docker run -it local/$(target):production /bin/sh


## DOCKER SWARM -------------------------------
#
# - All resolved configuration are named as .stack-${name}-*.yml to distinguish from docker-compose files which can be parametrized
#
SWARM_HOSTS            = $(shell docker node ls --format="{{.Hostname}}" 2>$(if $(IS_WIN),null,/dev/null))
docker-compose-configs = $(wildcard services/docker-compose*.yml)
CPU_COUNT = $(shell cat /proc/cpuinfo | grep processor | wc -l )

# NOTE: fore details on below SEE
# https://github.com/docker/compose/issues/7771#issuecomment-765243575
# below sed operation fixes above issue
# `sed -E "s/cpus: ([0-9\\.]+)/cpus: '\\1'/"`
# remove when this issues is fixed, this will most likely occur
# when upgrading the version of docker-compose

.stack-simcore-development.yml: .env $(docker-compose-configs)
	# Creating config for stack with 'local/{service}:development' to $@
	@export DOCKER_REGISTRY=local && \
	export DOCKER_IMAGE_TAG=development && \
	export DEV_PC_CPU_COUNT=${CPU_COUNT} && \
	scripts/docker/docker-compose-config.bash -e .env \
		services/docker-compose.yml \
		services/docker-compose.local.yml \
		services/docker-compose.devel.yml \
		> $@

.stack-simcore-production.yml: .env $(docker-compose-configs)
	# Creating config for stack with 'local/{service}:production' to $@
	@export DOCKER_REGISTRY=local && \
	export DOCKER_IMAGE_TAG=production && \
	scripts/docker/docker-compose-config.bash -e .env \
		services/docker-compose.yml \
		services/docker-compose.local.yml \
		> $@


.stack-simcore-development-frontend.yml: .env $(docker-compose-configs)
	# Creating config for stack with 'local/{service}:production' (except of static-webserver -> static-webserver:development) to $@
	@export DOCKER_REGISTRY=local && \
	export DOCKER_IMAGE_TAG=production && \
	scripts/docker/docker-compose-config.bash -e $< \
		services/docker-compose.yml \
		services/docker-compose.local.yml \
		services/docker-compose.devel-frontend.yml \
		> $@

.stack-simcore-version.yml: .env $(docker-compose-configs)
	# Creating config for stack with '$(DOCKER_REGISTRY)/{service}:${DOCKER_IMAGE_TAG}' to $@
	@scripts/docker/docker-compose-config.bash -e .env \
		services/docker-compose.yml \
		services/docker-compose.local.yml \
		> $@


.stack-ops.yml: .env $(docker-compose-configs)
	# Compiling config file for filestash
	$(eval TMP_PATH_TO_FILESTASH_CONFIG=$(shell set -o allexport && \
	source $(CURDIR)/.env && \
	set +o allexport && \
	python3 scripts/filestash/create_config.py))
	# Creating config for ops stack to $@
	# -> filestash config at $(TMP_PATH_TO_FILESTASH_CONFIG)
ifdef ops_ci
	@$(shell \
		export TMP_PATH_TO_FILESTASH_CONFIG="${TMP_PATH_TO_FILESTASH_CONFIG}" && \
		scripts/docker/docker-compose-config.bash -e .env \
		services/docker-compose-ops-ci.yml \
		> $@ \
	)
else
	@$(shell \
		export TMP_PATH_TO_FILESTASH_CONFIG="${TMP_PATH_TO_FILESTASH_CONFIG}" && \
		scripts/docker/docker-compose-config.bash -e .env \
		services/docker-compose-ops.yml \
		> $@ \
	)
endif



.PHONY: up-devel up-prod up-prod-ci up-version up-latest .deploy-ops

.deploy-ops: .stack-ops.yml
	# Deploy stack 'ops'
ifndef ops_disabled
	# -> filestash config at $(TMP_PATH_TO_FILESTASH_CONFIG)
	docker stack deploy --with-registry-auth -c $< ops
else
	@echo "Explicitly disabled with ops_disabled flag in CLI"
endif

define _show_endpoints
# The following endpoints are available
set -o allexport; \
source $(CURDIR)/.env; \
set +o allexport; \
separator=------------------------------------------------------------------------------------;\
separator=$${separator}$${separator}$${separator};\
rows="%-24s | %90s | %12s | %12s\n";\
TableWidth=140;\
printf "%24s | %90s | %12s | %12s\n" Name Endpoint User Password;\
printf "%.$${TableWidth}s\n" "$$separator";\
printf "$$rows" "oSparc platform" "http://$(get_my_ip).nip.io:9081";\
printf "$$rows" "oSparc web API doc" "http://$(get_my_ip).nip.io:9081/dev/doc";\
printf "$$rows" "oSparc public API doc" "http://$(get_my_ip).nip.io:8006/dev/doc";\
printf "$$rows" "Postgres DB" "http://$(get_my_ip).nip.io:18080/?pgsql=postgres&username="$${POSTGRES_USER}"&db="$${POSTGRES_DB}"&ns=public" $${POSTGRES_USER} $${POSTGRES_PASSWORD};\
printf "$$rows" "Portainer" "http://$(get_my_ip).nip.io:9000" admin adminadmin;\
printf "$$rows" "Redis" "http://$(get_my_ip).nip.io:18081";\
printf "$$rows" "Dask Dashboard" "http://$(get_my_ip).nip.io:8787";\
printf "$$rows" "Docker Registry" "$${REGISTRY_URL}" $${REGISTRY_USER} $${REGISTRY_PW};\
printf "$$rows" "Invitations" "http://$(get_my_ip).nip.io:8008/dev/doc" $${INVITATIONS_USERNAME} $${INVITATIONS_PASSWORD};\
printf "$$rows" "Payments" "http://$(get_my_ip).nip.io:8011/dev/doc" $${PAYMENTS_USERNAME} $${PAYMENTS_PASSWORD};\
printf "$$rows" "Rabbit Dashboard" "http://$(get_my_ip).nip.io:15672" admin adminadmin;\
printf "$$rows" "Traefik Dashboard" "http://$(get_my_ip).nip.io:8080/dashboard/";\
printf "$$rows" "Storage S3 Filestash" "http://$(get_my_ip).nip.io:9002" 12345678 12345678;\
printf "$$rows" "Storage S3 Minio" "http://$(get_my_ip).nip.io:9001" 12345678 12345678;\

printf "\n%s\n" "⚠️ if a DNS is not used (as displayed above), the interactive services started via dynamic-sidecar";\
echo "⚠️ will not be shown. The frontend accesses them via the uuid.services.YOUR_IP.nip.io:9081";
endef


show-endpoints:
	@$(_show_endpoints)

up-devel: .stack-simcore-development.yml .init-swarm $(CLIENT_WEB_OUTPUT) ## Deploys local development stack, qx-compile+watch and ops stack (pass 'make ops_disabled=1 up-...' to disable)
	# Start compile+watch front-end container [front-end]
	@$(MAKE_C) services/static-webserver/client down compile-dev flags=--watch
	# Deploy stack $(SWARM_STACK_NAME) [back-end]
	@docker stack deploy --with-registry-auth -c $< $(SWARM_STACK_NAME)
	@$(MAKE) .deploy-ops
	@$(_show_endpoints)
	@$(MAKE_C) services/static-webserver/client follow-dev-logs

up-devel-frontend: .stack-simcore-development-frontend.yml .init-swarm ## Every service in production except static-webserver. For front-end development
	# Start compile+watch front-end container [front-end]
	@$(MAKE_C) services/static-webserver/client down compile-dev flags=--watch
	# Deploy stack $(SWARM_STACK_NAME)  [back-end]
	@docker stack deploy --with-registry-auth -c $< $(SWARM_STACK_NAME)
	@$(MAKE) .deploy-ops
	@$(_show_endpoints)
	@$(MAKE_C) services/static-webserver/client follow-dev-logs


up-prod: .stack-simcore-production.yml .init-swarm ## Deploys local production stack and ops stack (pass 'make ops_disabled=1 ops_ci=1 up-...' to disable or target=<service-name> to deploy a single service)
ifeq ($(target),)
	# Deploy stack $(SWARM_STACK_NAME)
	@docker stack deploy --with-registry-auth -c $< $(SWARM_STACK_NAME)
	@$(MAKE) .deploy-ops
else
	# deploys ONLY $(target) service
	@docker compose --file $< up --detach $(target)
endif
	@$(_show_endpoints)

up-version: .stack-simcore-version.yml .init-swarm ## Deploys versioned stack '$(DOCKER_REGISTRY)/{service}:$(DOCKER_IMAGE_TAG)' and ops stack (pass 'make ops_disabled=1 up-...' to disable)
	# Deploy stack $(SWARM_STACK_NAME)
	@docker stack deploy --with-registry-auth -c $< $(SWARM_STACK_NAME)
	@$(MAKE) .deploy-ops
	@$(_show_endpoints)

up-latest:
	@export DOCKER_IMAGE_TAG=latest; \
	$(MAKE) up-version
	@$(_show_endpoints)


.PHONY: down leave
down: ## Stops and removes stack
	# Removing stacks in reverse order to creation
	-@$(foreach stack,\
		$(shell docker stack ls --format={{.Name}} | tac),\
		docker stack rm $(stack);)
	# Removing client containers (if any)
	-@$(MAKE_C) services/static-webserver/client down
	# Removing generated docker compose configurations, i.e. .stack-*
ifneq ($(wildcard .stack-*), )
	-@rm $(wildcard .stack-*)
endif
	# Removing local registry if any
	-@docker ps --all --quiet --filter "name=$(LOCAL_REGISTRY_HOSTNAME)" | xargs --no-run-if-empty docker rm

leave: ## Forces to stop all services, networks, etc by the node leaving the swarm
	-docker swarm leave -f


.PHONY: .init-swarm
.init-swarm:
	# Ensures swarm is initialized
	$(if $(SWARM_HOSTS),,docker swarm init --advertise-addr=$(get_my_ip))


## DOCKER TAGS  -------------------------------

.PHONY: tag-local tag-version tag-latest

tag-local: ## Tags version '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}' images as 'local/{service}:production'
	# Tagging all '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}' as 'local/{service}:production'
	@$(foreach service, $(SERVICES_NAMES_TO_BUILD)\
		,docker tag ${DOCKER_REGISTRY}/$(service):${DOCKER_IMAGE_TAG} local/$(service):production; \
	)

tag-version: ## Tags 'local/{service}:production' images as versioned '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}'
	# Tagging all 'local/{service}:production' as '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}'
	@$(foreach service, $(SERVICES_NAMES_TO_BUILD)\
		,docker tag local/$(service):production ${DOCKER_REGISTRY}/$(service):${DOCKER_IMAGE_TAG}; \
	)

tag-latest: ## Tags last locally built production images as '${DOCKER_REGISTRY}/{service}:latest'
	@export DOCKER_IMAGE_TAG=latest; \
	$(MAKE) tag-version



## DOCKER PULL/PUSH  -------------------------------
#
# TODO: cannot push modified/untracked
# TODO: cannot push disceted
#
.PHONY: pull-version

pull-version: .env ## pulls images from DOCKER_REGISTRY tagged as DOCKER_IMAGE_TAG
	# Pulling images '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}'
	@docker compose --file services/docker-compose-deploy.yml pull


.PHONY: push-version push-latest

push-latest: tag-latest
	@export DOCKER_IMAGE_TAG=latest; \
	$(MAKE) push-version

# below BUILD_TARGET gets overwritten but is required when merging yaml files
push-version: tag-version
	# pushing '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}'
	@export BUILD_TARGET=undefined; \
	docker compose --file services/docker-compose-build.yml --file services/docker-compose-deploy.yml push


## ENVIRONMENT -------------------------------

.PHONY: devenv devenv-all node-env

.venv:
	@python3 --version
	python3 -m venv $@
	## upgrading tools to latest version in $(shell python3 --version)
	$@/bin/pip3 --quiet install --upgrade \
		pip~=23.1 \
		wheel \
		setuptools
	@$@/bin/pip3 list --verbose

devenv: .venv .vscode/settings.json .vscode/launch.json ## create a development environment (configs, virtual-env, hooks, ...)
	$</bin/pip3 --quiet install -r requirements/devenv.txt
	# Installing pre-commit hooks in current .git repo
	@$</bin/pre-commit install
	@echo "To activate the venv, execute 'source .venv/bin/activate'"


devenv-all: devenv ## sets up extra development tools (everything else besides python)
	# Upgrading client compiler
	@$(MAKE_C) services/static-webserver/client upgrade
	# Building tools
	@$(MAKE_C) scripts/json-schema-to-openapi-schema


node_modules: package.json
	# checking npm installed
	@npm --version
	# installing package.json
	npm install --package-lock

nodenv: node_modules ## builds node_modules local environ (TODO)


.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)


.vscode/settings.json: .vscode/settings.template.json
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)


.vscode/launch.json: .vscode/launch.template.json
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)



## TOOLS -------------------------------

.PHONY: pylint


pylint: ## python linting
	# pylint version info
	@/bin/bash -c "pylint --version"
	# Running linter in packages and services (except director)
	@folders=$$(find $(CURDIR)/services $(CURDIR)/packages  -type d -not -path "*/director/*" -name 'src' -exec dirname {} \; | sort -u); \
	exit_status=0; \
	for folder in $$folders; do \
		pushd "$$folder"; \
		make pylint || exit_status=1; \
		popd; \
	done;\
	exit $$exit_status
	# Running linter elsewhere
	@pylint --rcfile=.pylintrc -v $(CURDIR)/tests --ignore=examples
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes

ruff: ## python ruffing
	# ruff version info
	@ruff --version
	# Running ruff in packages and services (except director)
	@ruff check \
		--config=$(CURDIR)/.ruff.toml \
		--respect-gitignore \
		--extend-exclude="**/tests" \
		--extend-exclude="**/generated_models" \
		--extend-exclude="**/director/" \
		$(CURDIR)/services \
		$(CURDIR)/packages

.PHONY: new-service
new-service: .venv ## Bakes a new project from cookiecutter-simcore-pyservice and drops it under services/ [UNDER DEV]
	$</bin/pip3 --quiet install cookiecutter
	.venv/bin/cookiecutter gh:itisfoundation/cookiecutter-simcore-pyservice --output-dir $(CURDIR)/services


.PHONY: openapi-specs
openapi-specs: ## bundles and validates openapi specifications and schemas of ALL service's API
	@$(MAKE_C) services/web/server $@
	@$(MAKE_C) services/storage $@


.PHONY: settings-schema.json
settings-schema.json: ## [container] dumps json-schema settings of all services
	@$(MAKE_C) services/agent $@
	@$(MAKE_C) services/api-server $@
	@$(MAKE_C) services/autoscaling $@
	@$(MAKE_C) services/catalog $@
	@$(MAKE_C) services/dask-sidecar $@
	@$(MAKE_C) services/datcore-adapter $@
	@$(MAKE_C) services/director-v2 $@
	@$(MAKE_C) services/invitations $@
	@$(MAKE_C) services/payments $@
	@$(MAKE_C) services/storage $@
	@$(MAKE_C) services/web/server $@


.PHONY: code-analysis
code-analysis: .codeclimate.yml ## runs code-climate analysis
	# Validates $<
	./scripts/code-climate.bash validate-config
	# Running analysis
	./scripts/code-climate.bash analyze


.PHONY: auto-doc
auto-doc: .stack-simcore-version.yml ## updates diagrams for README.md
	# Parsing docker compose config $< and creating graph
	@./scripts/docker-compose-viz.bash $<
	# Updating docs/img
	@mv --verbose $<.png docs/img/


.PHONY: postgres-upgrade
postgres-upgrade: ## initalize or upgrade postgres db to latest state
	@$(MAKE_C) packages/postgres-database/docker build
	@$(MAKE_C) packages/postgres-database/docker upgrade

.PHONY: CITATION-validate
CITATION-validate: ## validates CITATION.cff file
	@docker run --rm -v $(CURDIR):/app citationcff/cffconvert --validate

## LOCAL DOCKER REGISTRY (for local development only) -------------------------------

LOCAL_REGISTRY_HOSTNAME := registry
LOCAL_REGISTRY_VOLUME   := $(LOCAL_REGISTRY_HOSTNAME)

.PHONY: local-registry rm-registry

rm-registry: ## remove the registry and changes to host/file
	@$(if $(shell grep "127.0.0.1 $(LOCAL_REGISTRY_HOSTNAME)" /etc/hosts),\
		echo removing entry in /etc/hosts...;\
		sudo sed -i "/127.0.0.1 $(LOCAL_REGISTRY_HOSTNAME)/d" /etc/hosts,\
		echo /etc/hosts is already cleaned)
	@$(if $(shell jq -e '.["insecure-registries"]? | index("http://$(LOCAL_REGISTRY_HOSTNAME):5000")? // empty' /etc/docker/daemon.json),\
		echo removing entry in /etc/docker/daemon.json...;\
		jq 'if .["insecure-registries"] then .["insecure-registries"] |= map(select(. != "http://$(LOCAL_REGISTRY_HOSTNAME):5000")) else . end' /etc/docker/daemon.json > /tmp/daemon.json && \
		sudo mv /tmp/daemon.json /etc/docker/daemon.json &&\
		echo restarting engine... &&\
		sudo service docker restart &&\
		echo done,\
		echo /etc/docker/daemon.json already cleaned)
	# removing container and volume
	-@docker rm --force $(LOCAL_REGISTRY_HOSTNAME)
	-@docker volume rm $(LOCAL_REGISTRY_VOLUME)

local-registry: .env ## creates a local docker registry and configure simcore to use it (NOTE: needs admin rights)
	@$(if $(shell grep "127.0.0.1 $(LOCAL_REGISTRY_HOSTNAME)" /etc/hosts),,\
					echo configuring host file to redirect $(LOCAL_REGISTRY_HOSTNAME) to 127.0.0.1; \
					sudo echo 127.0.0.1 $(LOCAL_REGISTRY_HOSTNAME) | sudo tee -a /etc/hosts;\
					echo done)
	@$(if $(shell jq -e '.["insecure-registries"]? | index("http://$(LOCAL_REGISTRY_HOSTNAME):5000")? // empty' /etc/docker/daemon.json),,\
					echo configuring docker engine to use insecure local registry...; \
					jq 'if .["insecure-registries"] | index("http://$(LOCAL_REGISTRY_HOSTNAME):5000") then . else .["insecure-registries"] += ["http://$(LOCAL_REGISTRY_HOSTNAME):5000"] end' /etc/docker/daemon.json > /tmp/daemon.json &&\
					sudo mv /tmp/daemon.json /etc/docker/daemon.json &&\
					echo restarting engine... &&\
					sudo service docker restart &&\
					echo done)

	@$(if $(shell docker ps --format="{{.Names}}" | grep registry),,\
					echo starting registry on http://$(LOCAL_REGISTRY_HOSTNAME):5000...; \
					docker run \
							--detach \
							--init \
							--env REGISTRY_STORAGE_DELETE_ENABLED=true \
							--publish 5000:5000 \
							--volume $(LOCAL_REGISTRY_VOLUME):/var/lib/registry \
							--name $(LOCAL_REGISTRY_HOSTNAME) \
							registry:2)

	# WARNING: environment file .env is now setup to use local registry on port 5000 without any security (take care!)...
	@echo REGISTRY_AUTH=False >> .env
	@echo REGISTRY_SSL=False >> .env
	@echo REGISTRY_PATH=$(LOCAL_REGISTRY_HOSTNAME):5000 >> .env
	@echo REGISTRY_URL=$(get_my_ip):5000 >> .env
	@echo DIRECTOR_REGISTRY_CACHING=False >> .env
	@echo CATALOG_BACKGROUND_TASK_REST_TIME=1 >> .env
	# local registry set in $(LOCAL_REGISTRY_HOSTNAME):5000
	# images currently in registry:
	@sleep 3
	curl --silent $(LOCAL_REGISTRY_HOSTNAME):5000/v2/_catalog | jq '.repositories'

info-registry: ## info on local registry (if any)
	# ping API
	curl --silent $(LOCAL_REGISTRY_HOSTNAME):5000/v2
	# list all
	curl --silent $(LOCAL_REGISTRY_HOSTNAME):5000/v2/_catalog | jq
	# target detail info (if set)
	$(if $(target),\
	@echo Tags for $(target); \
	curl --silent $(LOCAL_REGISTRY_HOSTNAME):5000/v2/$(target)/tags/list | jq ,\
	@echo No target set)


## INFO -------------------------------

.PHONY: info info-images info-swarm  info-tools
info: ## displays setup information
	# setup info:
	@echo ' Detected OS          : $(IS_LINUX)$(IS_OSX)$(IS_WSL)$(IS_WSL2)$(IS_WIN)'
	@echo ' SWARM_STACK_NAME     : ${SWARM_STACK_NAME}'
	@echo ' DOCKER_REGISTRY      : $(DOCKER_REGISTRY)'
	@echo ' DOCKER_IMAGE_TAG     : ${DOCKER_IMAGE_TAG}'
	@echo ' BUILD_DATE           : ${BUILD_DATE}'
	@echo ' VCS_* '
	@echo '  - ULR                : ${VCS_URL}'
	@echo '  - REF                : ${VCS_REF}'
	@echo '  - (STATUS)REF_CLIENT : (${VCS_STATUS_CLIENT}) ${VCS_REF_CLIENT}'
	@echo ' DIRECTOR_API_VERSION  : ${DIRECTOR_API_VERSION}'
	@echo ' STORAGE_API_VERSION   : ${STORAGE_API_VERSION}'
	@echo ' DATCORE_ADAPTER_API_VERSION   : ${DATCORE_ADAPTER_API_VERSION}'
	@echo ' WEBSERVER_API_VERSION : ${WEBSERVER_API_VERSION}'
	# dev tools version
	@echo ' make          : $(shell make --version 2>&1 | head -n 1)'
	@echo ' jq            : $(shell jq --version)'
	@echo ' awk           : $(shell awk -W version 2>&1 | head -n 1)'
	@echo ' python        : $(shell python3 --version)'
	@echo ' node          : $(shell node --version 2> /dev/null || echo ERROR nodejs missing)'
	@echo ' docker        : $(shell docker --version)'
	@echo ' docker buildx : $(shell docker buildx version)'
	@echo ' docker compose: $(shell docker compose version)'


define show-meta
	$(foreach iid,$(shell docker images */$(1):* -q | sort | uniq),\
		docker image inspect $(iid) | jq '.[0] | .RepoTags, .Config.Labels, .Architecture';)
endef

info-images:  ## lists tags and labels of built images. To display one: 'make target=webserver info-images'
ifeq ($(target),)
	@$(foreach service,$(SERVICES_NAMES_TO_BUILD),\
		echo "## $(service) images:";\
			docker images */$(service):*;\
			$(call show-meta,$(service))\
		)
else
	## $(target) images:
	@$(call show-meta,$(target))
endif

info-swarm: ## displays info about stacks and networks
ifneq ($(SWARM_HOSTS), )
	# Stacks in swarm
	@docker stack ls
	# Containers (tasks) running in '$(SWARM_STACK_NAME)' stack
	-@docker stack ps $(SWARM_STACK_NAME)
	# Services in '$(SWARM_STACK_NAME)' stack
	-@docker stack services $(SWARM_STACK_NAME)
	# Services in 'ops' stack
	-@docker stack services ops
	# Networks
	@docker network ls
endif



## CLEAN -------------------------------

.PHONY: clean clean-images clean-venv clean-all clean-more

_git_clean_args := -dx --force --exclude=.vscode --exclude=TODO.md --exclude=.venv --exclude=.python-version --exclude="*keep*"
_running_containers = $(shell docker ps -aq)

.check-clean:
	@git clean -n $(_git_clean_args)
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo -n "$(shell whoami), are you REALLY sure? [y/N] " && read ans && [ $${ans:-N} = y ]

clean-venv: devenv ## Purges .venv into original configuration
	# Cleaning your venv
	.venv/bin/pip-sync --quiet $(CURDIR)/requirements/devenv.txt
	@pip list

clean-hooks: ## Uninstalls git pre-commit hooks
	@-pre-commit uninstall 2> /dev/null || rm .git/hooks/pre-commit

clean: .check-clean ## cleans all unversioned files in project and temp files create by this makefile
	# Cleaning unversioned
	@git clean $(_git_clean_args)
	# Cleaning static-webserver/client
	@$(MAKE_C) services/static-webserver/client clean-files

clean-more: ## cleans containers and unused volumes
	# pruning unused volumes
	-@docker volume prune --force
	# pruning buildx cache
	-@docker buildx prune --force
	# stops and deletes running containers
	@$(if $(_running_containers), docker rm --force $(_running_containers),)

clean-images: ## removes all created images
	# Cleaning all service images
	-$(foreach service,$(SERVICES_NAMES_TO_BUILD)\
		,docker image rm --force $(shell docker images */$(service):* -q);)
	# Cleaning webclient
	-@$(MAKE_C) services/static-webserver/client clean-images
	# Cleaning postgres maintenance
	@$(MAKE_C) packages/postgres-database/docker clean

clean-all: clean clean-more clean-images clean-hooks # Deep clean including .venv and produced images
	-rm -rf .venv


.PHONY: reset
reset: ## restart docker daemon (LINUX ONLY)
	sudo systemctl restart docker


# RELEASE --------------------------------------------------------------------------------------------------------------------------------------------

staging_prefix := staging_
prod_prefix := v
_git_get_current_branch = $(shell git rev-parse --abbrev-ref HEAD)
# NOTE: be careful that GNU Make replaces newlines with space which is why this command cannot work using a Make function
_url_encoded_title = $(if $(findstring -staging, $@),Staging%20$(name),)$(version)
_url_encoded_tag = $(if $(findstring -staging, $@),$(staging_prefix)$(name),$(prod_prefix))$(version)
_url_encoded_target = $(if $(git_sha),$(git_sha),$(if $(findstring -hotfix, $@),$(_git_get_current_branch),master))
_prettify_logs = $$(git log \
		$$(git describe --match="$(if $(findstring -staging, $@),$(staging_prefix),$(prod_prefix))*" --abbrev=0 --tags)..$(if $(git_sha),$(git_sha),HEAD) \
		--pretty=format:"- %s")
define _url_encoded_logs
$(shell \
	scripts/url-encoder.bash \
	"$(_prettify_logs)"\
)
endef
_git_get_repo_orga_name = $(shell git config --get remote.origin.url | \
							grep --perl-regexp --only-matching "((?<=git@github\.com:)|(?<=https:\/\/github\.com\/))(.*?)(?=.git)")

.PHONY: .check-on-master-branch .create_github_release_url
.check-on-master-branch:
	@if [ "$(_git_get_current_branch)" != "master" ]; then\
		echo -e "\e[91mcurrent branch is not master branch."; exit 1;\
	fi

define create_github_release_url
	# ensure tags are uptodate
	git pull --tags && \
	echo -e "\e[33mOpen the following link to create the $(if $(findstring -staging, $@),staging,production) release:" && \
	echo -e "\e[32mhttps://github.com/$(_git_get_repo_orga_name)/releases/new?prerelease=$(if $(findstring -staging, $@),1,0)&target=$(_url_encoded_target)&tag=$(_url_encoded_tag)&title=$(_url_encoded_title)&body=$(_url_encoded_logs)" && \
	echo -e "\e[33mOr open the following link to create the $(if $(findstring -staging, $@),staging,production) release and paste the logs:" && \
	echo -e "\e[32mhttps://github.com/$(_git_get_repo_orga_name)/releases/new?prerelease=$(if $(findstring -staging, $@),1,0)&target=$(_url_encoded_target)&tag=$(_url_encoded_tag)&title=$(_url_encoded_title)" && \
	echo -e "\e[34m$(_prettify_logs)"
endef

.PHONY: release-staging release-prod
release-staging release-prod: .check-on-master-branch  ## Helper to create a staging or production release in Github (usage: make release-staging name=sprint version=1 git_sha=optional or make release-prod version=1.2.3 git_sha=mandatory)
	$(create_github_release_url)

.PHONY: release-hotfix release-staging-hotfix
release-hotfix release-staging-hotfix: ## Helper to create a hotfix release in Github (usage: make release-hotfix version=1.2.4 git_sha=optional or make release-staging-hotfix name=Sprint version=2)
	$(create_github_release_url)

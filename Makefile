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
# TODO: read from docker-compose file instead $(shell find  $(CURDIR)/services -type f -name 'Dockerfile')
# or $(notdir $(subst /Dockerfile,,$(wildcard services/*/Dockerfile))) ...
SERVICES_LIST := \
	api-server \
	catalog \
	dask-sidecar \
	datcore-adapter \
	director \
	director-v2 \
	dynamic-sidecar \
	migration \
	static-webserver \
	storage \
	webserver

CLIENT_WEB_OUTPUT       := $(CURDIR)/services/web/client/source-output

# version control
export VCS_URL          := $(shell git config --get remote.origin.url)
export VCS_REF          := $(shell git rev-parse --short HEAD)
export VCS_REF_CLIENT   := $(shell git log --pretty=tformat:"%h" -n1 services/web/client)
export VCS_STATUS_CLIENT:= $(if $(shell git status -s),'modified/untracked','clean')
export BUILD_DATE       := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

# api-versions
export API_SERVER_API_VERSION := $(shell cat $(CURDIR)/services/api-server/VERSION)
export CATALOG_API_VERSION    := $(shell cat $(CURDIR)/services/catalog/VERSION)
export DIRECTOR_API_VERSION   := $(shell cat $(CURDIR)/services/director/VERSION)
export DIRECTOR_V2_API_VERSION:= $(shell cat $(CURDIR)/services/director-v2/VERSION)
export STORAGE_API_VERSION    := $(shell cat $(CURDIR)/services/storage/VERSION)
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
S3_ENDPOINT := $(get_my_ip):9001
export S3_ENDPOINT



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

define _docker_compose_build
export BUILD_TARGET=$(if $(findstring -devel,$@),development,production);\
pushd services && docker buildx bake --file docker-compose-build.yml $(if $(target),$(target),) && popd;
endef

rebuild: build-nc # alias
build build-nc: .env ## Builds production images and tags them as 'local/{service-name}:production'. For single target e.g. 'make target=webserver build'
ifeq ($(target),)
	# Compiling front-end
	$(MAKE_C) services/web/client compile

	# Building services
	$(_docker_compose_build)
else
ifeq ($(findstring static-webserver,$(target)),static-webserver)
	# Compiling front-end
	$(MAKE_C) services/web/client clean compile
endif
	# Building service $(target)
	$(_docker_compose_build)
endif


build-devel build-devel-nc: .env ## Builds development images and tags them as 'local/{service-name}:development'. For single target e.g. 'make target=webserver build-devel'
ifeq ($(target),)
	# Building services
	$(_docker_compose_build)
else
ifeq ($(findstring static-webserver,$(target)),static-webserver)
	# Compiling front-end
	$(MAKE_C) services/web/client touch compile-dev
endif
	# Building service $(target)
	@$(_docker_compose_build)
endif


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

.stack-simcore-development.yml: .env $(docker-compose-configs)
	# Creating config for stack with 'local/{service}:development' to $@
	@export DOCKER_REGISTRY=local \
	export DOCKER_IMAGE_TAG=development; \
	export DEV_PC_CPU_COUNT=${CPU_COUNT}; \
	docker-compose --env-file .env --file services/docker-compose.yml --file services/docker-compose.local.yml --file services/docker-compose.devel.yml --log-level=ERROR config > $@

.stack-simcore-production.yml: .env $(docker-compose-configs)
	# Creating config for stack with 'local/{service}:production' to $@
	@export DOCKER_REGISTRY=local;       \
	export DOCKER_IMAGE_TAG=production; \
	docker-compose --env-file .env --file services/docker-compose.yml --file services/docker-compose.local.yml --log-level=ERROR config > $@

.stack-simcore-version.yml: .env $(docker-compose-configs)
	# Creating config for stack with '$(DOCKER_REGISTRY)/{service}:${DOCKER_IMAGE_TAG}' to $@
	@docker-compose --env-file .env --file services/docker-compose.yml --file services/docker-compose.local.yml --log-level=ERROR config > $@

.stack-ops.yml: .env $(docker-compose-configs)
	# Creating config for ops stack to $@
	@docker-compose --env-file .env --file services/docker-compose-ops.yml --log-level=ERROR config > $@


.PHONY: up-devel up-prod up-version up-latest .deploy-ops

.deploy-ops: .stack-ops.yml
	# Deploy stack 'ops'
ifndef ops_disabled
	@docker stack deploy --with-registry-auth -c $< ops
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
rows="%-22s | %90s | %12s | %12s\n";\
TableWidth=140;\
printf "%22s | %90s | %12s | %12s\n" Name Endpoint User Password;\
printf "%.$${TableWidth}s\n" "$$separator";\
printf "$$rows" 'oSparc platform' 'http://$(get_my_ip).nip.io:9081';\
printf "$$rows" 'Postgres DB' 'http://$(get_my_ip).nip.io:18080/?pgsql=postgres&username='$${POSTGRES_USER}'&db='$${POSTGRES_DB}'&ns=public' $${POSTGRES_USER} $${POSTGRES_PASSWORD};\
printf "$$rows" Portainer 'http://$(get_my_ip).nip.io:9000' admin adminadmin;\
printf "$$rows" Redis 'http://$(get_my_ip).nip.io:18081';\
printf "$$rows" 'Docker Registry' $${REGISTRY_URL} $${REGISTRY_USER} $${REGISTRY_PW};\
printf "$$rows" "Dask Dashboard" "http://$(if $(IS_WSL2),$(get_my_ip),127.0.0.1).nip.io:8787";
printf "\n%s\n" "⚠️ if a DNS is not used (as displayed above), the interactive services started via dynamic-sidecar";\
echo "⚠️ will not be shown. The frontend accesses them via the uuid.services.YOUR_IP.nip.io:9081";
endef

show-endpoints:
	@$(_show_endpoints)

up-devel: .stack-simcore-development.yml .init-swarm $(CLIENT_WEB_OUTPUT) ## Deploys local development stack, qx-compile+watch and ops stack (pass 'make ops_disabled=1 up-...' to disable)
	# Start compile+watch front-end container [front-end]
	@$(MAKE_C) services/web/client down compile-dev flags=--watch
	# Deploy stack $(SWARM_STACK_NAME) [back-end]
	@docker stack deploy --with-registry-auth -c $< $(SWARM_STACK_NAME)
	@$(MAKE) .deploy-ops
	@$(_show_endpoints)
	@$(MAKE_C) services/web/client follow-dev-logs


up-prod: .stack-simcore-production.yml .init-swarm ## Deploys local production stack and ops stack (pass 'make ops_disabled=1 up-...' to disable or target=<service-name> to deploy a single service)
ifeq ($(target),)
	# Deploy stack $(SWARM_STACK_NAME)
	@docker stack deploy --with-registry-auth -c $< $(SWARM_STACK_NAME)
	@$(MAKE) .deploy-ops
else
	# deploys ONLY $(target) service
	@docker-compose --file $< up --detach $(target)
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
	-@$(MAKE_C) services/web/client down
	# Removing generated docker compose configurations, i.e. .stack-*
	-@rm $(wildcard .stack-*)
	# Removing local registry if any
	-@docker rm --force $(local_registry)

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
	@$(foreach service, $(SERVICES_LIST)\
		,docker tag ${DOCKER_REGISTRY}/$(service):${DOCKER_IMAGE_TAG} local/$(service):production; \
	)

tag-version: ## Tags 'local/{service}:production' images as versioned '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}'
	# Tagging all 'local/{service}:production' as '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}'
	@$(foreach service, $(SERVICES_LIST)\
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
	@docker-compose --file services/docker-compose-deploy.yml pull


.PHONY: push-version push-latest

push-latest: tag-latest
	@export DOCKER_IMAGE_TAG=latest; \
	$(MAKE) push-version

# below BUILD_TARGET gets overwritten but is required when merging yaml files
push-version: tag-version
	# pushing '${DOCKER_REGISTRY}/{service}:${DOCKER_IMAGE_TAG}'
	@export BUILD_TARGET=undefined; \
	docker-compose --file services/docker-compose-build.yml --file services/docker-compose-deploy.yml push


## ENVIRONMENT -------------------------------

.PHONY: devenv devenv-all node-env

.venv:
	python3 -m venv $@
	$@/bin/pip3 --quiet install --upgrade \
		pip \
		wheel \
		setuptools

devenv: .venv ## create a python virtual environment with dev tools (e.g. linters, etc)
	$</bin/pip3 --quiet install -r requirements/devenv.txt
	# Installing pre-commit hooks in current .git repo
	@$</bin/pre-commit install
	@echo "To activate the venv, execute 'source .venv/bin/activate'"


devenv-all: devenv ## sets up extra development tools (everything else besides python)
	# Upgrading client compiler
	@$(MAKE_C) services/web/client upgrade
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


.vscode/settings.json: .vscode-template/settings.json
	$(info WARNING: #####  $< is newer than $@ ####)
	@diff -uN $@ $<
	@false



## TOOLS -------------------------------

.PHONY: pylint

pylint: ## Runs python linter framework's wide
	# pylint version info
	@/bin/bash -c "pylint --version"
	# Running linter
	@/bin/bash -c "pylint --jobs=0 --rcfile=.pylintrc $(strip $(shell find services packages -iname '*.py' \
											-not -path "*ignore*" \
											-not -path "*.venv*" \
											-not -path "*/client/*" \
											-not -path "*egg*" \
											-not -path "*migration*" \
											-not -path "*datcore.py" \
											-not -path "*sandbox*" \
											-not -path "*-sdk/python*" \
											-not -path "*generated_code*" \
											-not -path "*build*" \
											-not -path "*datcore.py" \
											-not -path "*web/server*"))"
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes


.PHONY: new-service
new-service: .venv ## Bakes a new project from cookiecutter-simcore-pyservice and drops it under services/ [UNDER DEV]
	$</bin/pip3 --quiet install cookiecutter
	.venv/bin/cookiecutter gh:itisfoundation/cookiecutter-simcore-pyservice --output-dir $(CURDIR)/services


.PHONY: openapi-specs
openapi-specs: ## bundles and validates openapi specifications and schemas of ALL service's API
	@$(MAKE_C) services/web/server $@
	@$(MAKE_C) services/storage $@
	@$(MAKE_C) services/director $@


.PHONY: code-analysis
code-analysis: .codeclimate.yml ## runs code-climate analysis
	# Validates $<
	./scripts/code-climate.bash validate-config
	# Running analysis
	./scripts/code-climate.bash analyze


.PHONY: auto-doc
auto-doc: .stack-simcore-version.yml ## updates diagrams for README.md
	# Parsing docker-compose config $< and creating graph
	@./scripts/docker-compose-viz.bash $<
	# Updating docs/img
	@mv --verbose $<.png docs/img/


.PHONY: postgres-upgrade
postgres-upgrade: ## initalize or upgrade postgres db to latest state
	@$(MAKE_C) packages/postgres-database/docker build
	@$(MAKE_C) packages/postgres-database/docker upgrade


local_registry=registry
.PHONY: local-registry rm-registry

rm-registry: ## remove the registry and changes to host/file
	@$(if $(shell grep "127.0.0.1 $(local_registry)" /etc/hosts),\
		echo removing entry in /etc/hosts...;\
		sudo sed -i "/127.0.0.1 $(local_registry)/d" /etc/hosts,\
		echo /etc/hosts is already cleaned)
	@$(if $(shell grep "{\"insecure-registries\": \[\"$(local_registry):5000\"\]}" /etc/docker/daemon.json),\
		echo removing entry in /etc/docker/daemon.json...;\
		sudo sed -i '/{"insecure-registries": \["$(local_registry):5000"\]}/d' /etc/docker/daemon.json;,\
		echo /etc/docker/daemon.json is already cleaned)




local-registry: .env ## creates a local docker registry and configure simcore to use it (NOTE: needs admin rights)
	@$(if $(shell grep "127.0.0.1 $(local_registry)" /etc/hosts),,\
					echo configuring host file to redirect $(local_registry) to 127.0.0.1; \
					sudo echo 127.0.0.1 $(local_registry) | sudo tee -a /etc/hosts;\
					echo done)
	@$(if $(shell grep "{\"insecure-registries\": \[\"registry:5000\"\]}" /etc/docker/daemon.json),,\
					echo configuring docker engine to use insecure local registry...; \
					sudo echo {\"insecure-registries\": [\"$(local_registry):5000\"]} | sudo tee -a /etc/docker/daemon.json; \
					echo restarting engine...; \
					sudo service docker restart;\
					echo done)
	@$(if $(shell docker ps --format="{{.Names}}" | grep registry),,\
					echo starting registry on $(local_registry):5000...; \
					docker run --detach \
							--init \
							--publish 5000:5000 \
							--volume $(local_registry):/var/lib/registry \
							--name $(local_registry) \
							registry:2)

	# WARNING: environment file .env is now setup to use local registry on port 5000 without any security (take care!)...
	@echo REGISTRY_AUTH=False >> .env
	@echo REGISTRY_SSL=False >> .env
	@echo REGISTRY_PATH=$(local_registry):5000 >> .env
	@echo REGISTRY_URL=$(get_my_ip):5000 >> .env
	@echo DIRECTOR_REGISTRY_CACHING=False >> .env
	@echo CATALOG_BACKGROUND_TASK_REST_TIME=1 >> .env
	# local registry set in $(local_registry):5000
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
	@echo ' docker-compose: $(shell docker-compose --version)'


define show-meta
	$(foreach iid,$(shell docker images */$(1):* -q | sort | uniq),\
		docker image inspect $(iid) | jq '.[0] | .RepoTags, .ContainerConfig.Labels';)
endef

info-images:  ## lists tags and labels of built images. To display one: 'make target=webserver info-images'
ifeq ($(target),)
	@$(foreach service,$(SERVICES_LIST),\
		echo "## $(service) images:";\
			docker images */$(service):*;\
			$(call show-meta,$(service))\
		)
	## Client images:
	@$(MAKE_C) services/web/client info
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

_git_clean_args := -dx --force --exclude=.vscode --exclude=TODO.md --exclude=.venv --exclude=.python-version --exclude=*keep*
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
	# Cleaning web/client
	@$(MAKE_C) services/web/client clean-files

clean-more: ## cleans containers and unused volumes
	# stops and deletes running containers
	@$(if $(_running_containers), docker rm --force $(_running_containers),)
	# pruning unused volumes
	docker volume prune --force

clean-images: ## removes all created images
	# Cleaning all service images
	-$(foreach service,$(SERVICES_LIST)\
		,docker image rm --force $(shell docker images */$(service):* -q);)
	# Cleaning webclient
	@$(MAKE_C) services/web/client clean-images
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

.create_github_release_url:
	# ensure tags are uptodate
	@git pull --tags
	@echo -e "\e[33mOpen the following link to create the $(if $(findstring -staging, $@),staging,production) release:";
	@echo -e "\e[32mhttps://github.com/$(_git_get_repo_orga_name)/releases/new?prerelease=$(if $(findstring -staging, $@),1,0)&target=$(_url_encoded_target)&tag=$(_url_encoded_tag)&title=$(_url_encoded_title)&body=$(_url_encoded_logs)";
	@echo -e "\e[33mOr open the following link to create the $(if $(findstring -staging, $@),staging,production) release and paste the logs:";
	@echo -e "\e[32mhttps://github.com/$(_git_get_repo_orga_name)/releases/new?prerelease=$(if $(findstring -staging, $@),1,0)&target=$(_url_encoded_target)&tag=$(_url_encoded_tag)&title=$(_url_encoded_title)";
	@echo -e "\e[34m$(_prettify_logs)"
.PHONY: release-staging release-prod
release-staging release-prod: .check-on-master-branch .create_github_release_url ## Helper to create a staging or production release in Github (usage: make release-staging name=sprint version=1 git_sha=optional or make release-prod version=1.2.3 git_sha=optional)

.PHONY: release-hotfix release-staging-hotfix
release-hotfix release-staging-hotfix: .create_github_release_url## Helper to create a hotfix release in Github (usage: make release-hotfix version=1.2.4 git_sha=optional or make release-staging-hotfix name=Sprint version=2)

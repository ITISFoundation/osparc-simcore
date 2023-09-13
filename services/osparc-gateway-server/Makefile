#
# Targets for DEVELOPMENT for osparc gateway service service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile



APP_PACKAGE_NAME=osparc_gateway_server
SERVICE_NAME=osparc-gateway-server
DASK_SIDECAR_NAME=dask-sidecar

.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)



##
## INFOS
##
.PHONY: info-images info-swarm
define show-meta
	$(foreach iid,$(shell docker images "*/$(1):*" --quiet | sort | uniq),\
		docker image inspect $(iid) | jq '.[0] | {tags:.RepoTags, labels:.Config.Labels, arch:.Architecture}';)
endef

info-images:  ## lists tags and labels of built images. To display one: 'make target=webserver info-images'
	@echo "## $(SERVICE_NAME) images:";\
		docker images */$(SERVICE_NAME):*;\
		$(call show-meta,$(SERVICE_NAME))
	@echo "## $(DASK_SIDECAR_NAME) images:";\
		docker images */$(DASK_SIDECAR_NAME):*;\
		$(call show-meta,$(DASK_SIDECAR_NAME))


info-swarm: ## displays info about stacks and networks
ifneq ($(SWARM_HOSTS), )
	# Stacks in swarm
	@docker stack ls
	# Containers (tasks) running in '$(SWARM_STACK_NAME)' stack
	-@docker stack ps $(SWARM_STACK_NAME)
	# Services in '$(SWARM_STACK_NAME)' stack
	-@docker stack services $(SWARM_STACK_NAME)
	# Networks
	@docker network ls
endif

##
## Running Osparc Dask Gateway
##
SWARM_HOSTS = $(shell docker node ls --format="{{.Hostname}}" 2>$(if $(IS_WIN),NUL,/dev/null))

PHONY: .init-swarm
.init-swarm:
	# Ensures swarm is initialized
	$(if $(SWARM_HOSTS),,docker swarm init --advertise-addr=$(get_my_ip))

.PHONY: config
export OSPARC_GATEWAY_CONFIG_FILE_HOST = .osparc-dask-gateway-config.py
export SWARM_STACK_NAME ?= dask-gateway
docker-compose-config-cmd=../../scripts/docker/docker-compose-config.bash
docker-compose-configs = $(wildcard services/docker-compose*.yml)

$(OSPARC_GATEWAY_CONFIG_FILE_HOST): $(CURDIR)/config/default_config.py  ## creates config file from defaults in /config/default_config.py
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)
config: $(OSPARC_GATEWAY_CONFIG_FILE_HOST)  ## create default configuration file

.stack-$(SWARM_STACK_NAME)-development.yml: .env $(docker-compose-configs)
	# Creating config for stack with 'local/{service}:development' to $@
	@export DOCKER_REGISTRY=local && \
	export DOCKER_IMAGE_TAG=development && \
	$(docker-compose-config-cmd) \
	docker-compose.yml \
	docker-compose.local.yml \
	docker-compose.devel.yml > $@


.stack-$(SWARM_STACK_NAME)-production.yml: .env $(docker-compose-configs)
	# Creating config for stack with 'local/{service}:production' to $@
	@export DOCKER_REGISTRY=local && \
	export DOCKER_IMAGE_TAG=production && \
	$(docker-compose-config-cmd) \
	docker-compose.yml \
	docker-compose.local.yml > $@

.stack-$(SWARM_STACK_NAME)-version.yml: .env $(docker-compose-configs)
	# Creating config for stack with '$(DOCKER_REGISTRY)/{service}:${DOCKER_IMAGE_TAG}' to $@
	$(docker-compose-config-cmd) \
	docker-compose.yml \
	docker-compose.local.yml > $@


.PHONY: up-devel up-prod up-version up-latest

define _show_endpoints
# The following endpoints are available
set -o allexport; \
source $(CURDIR)/.env; \
set +o allexport; \
separator=------------------------------------------------------------------------------------;\
separator=$${separator}$${separator}$${separator};\
rows="%-22s | %40s | %12s | %12s\n";\
TableWidth=100;\
printf "%22s | %40s | %12s | %12s\n" Name Endpoint User Password;\
printf "%.$${TableWidth}s\n" "$$separator";\
printf "$$rows" Dask-Gateway 'http://$(get_my_ip):8000' whatever $(filter-out %.password =,$(shell cat $(OSPARC_GATEWAY_CONFIG_FILE_HOST) | grep c.Authenticator.password));
endef

show-endpoints:
	@$(_show_endpoints)


up-devel: .stack-$(SWARM_STACK_NAME)-development.yml .init-swarm config  ## Deploys local development stack and ops stack (pass 'make ops_disabled=1 up-...' to disable)
	# Deploy stack $(SWARM_STACK_NAME) [back-end]
	@docker stack deploy --with-registry-auth -c $< $(SWARM_STACK_NAME)
	@$(_show_endpoints)

up-prod: .stack-$(SWARM_STACK_NAME)-production.yml .init-swarm config ## Deploys local production stack and ops stack (pass 'make ops_disabled=1 up-...' to disable)
ifeq ($(target),)
	# Deploy stack $(SWARM_STACK_NAME)
	@docker stack deploy --with-registry-auth -c $< $(SWARM_STACK_NAME)
else
	# deploys ONLY $(target) service
	@docker compose --file $< up --detach $(target)
endif
	@$(_show_endpoints)

up up-version: .stack-$(SWARM_STACK_NAME)-version.yml .init-swarm config ## Deploys versioned stack '$(DOCKER_REGISTRY)/{service}:$(DOCKER_IMAGE_TAG)' and ops stack (pass 'make ops_disabled=1 up-...' to disable)
	# Deploy stack $(SWARM_STACK_NAME)
	@docker stack deploy --with-registry-auth -c $< $(SWARM_STACK_NAME)
	@$(_show_endpoints)

up-latest:
	@export DOCKER_IMAGE_TAG=release-github-latest && \
	$(MAKE) up-version

.PHONY: down
down: ## Stops and removes stack
	# Removing stacks in reverse order to creation
	-@docker stack rm $(SWARM_STACK_NAME)
	-@docker stack rm $(SWARM_STACK_NAME)-ops
	# Removing generated docker compose configurations, i.e. .stack-*
	-@rm $(wildcard .stack-*)
	-@rm $(wildcard $(OSPARC_GATEWAY_CONFIG_FILE_HOST))

##
## system tests
##
test-system: ## Runs system tests (needs local docker images of osparc-gateway-server and dask-sidecar)
	$(MAKE_C) tests/system install-ci
	$(MAKE_C) tests/system tests

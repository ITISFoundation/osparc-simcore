#
# DEVELOPMENT recipes for Auto scaling service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile



.PHONY: up-devel down
up-devel: .env ## starts local test application (running bare metal against AWS)
	# setting up dependencies
	@docker compose up

down: .env ## stops local test app dependencies (running bare metal against AWS)
	-@docker compose down


PHONY: .init-swarm
.init-swarm:
	# Ensures swarm is initialized (careful we use a default pool of 172.20.0.0/14. Ensure you do not use private IPs in that range!)
	$(if $(SWARM_HOSTS),,docker swarm init --advertise-addr=$(get_my_ip) --default-addr-pool 172.20.0.0/14)


.PHONY: test-dask-scheduler-deploy
deploy-dask-stack: .init-swarm ## deploy the dask stack for local testing
	# using local/dask-sidecar:production images
	@DOCKER_IMAGE_TAG=production \
	DOCKER_REGISTRY=local \
	LOG_LEVEL=INFO \
	docker stack deploy --with-registry-auth --compose-file=src/simcore_service_clusters_keeper/data/docker-compose.yml osparc_dask_stack

down-dask-stack: ## removes the dask stack
	# stopping dask stack
	-@docker stack rm osparc_dask_stack

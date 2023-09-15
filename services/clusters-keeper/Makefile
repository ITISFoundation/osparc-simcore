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

.PHONY: test-dask-schduler-deploy
test-dask-scheduler-deploy:
	# using local/dask-sidecar:production images
	@DOCKER_IMAGE_TAG=production \
	DOCKER_REGISTRY=local \
	LOG_LEVEL=INFO \
	docker compose --file=src/simcore_service_clusters_keeper/data/docker-compose.yml up

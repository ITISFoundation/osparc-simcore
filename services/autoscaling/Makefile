#
# DEVELOPMENT recipes for Auto scaling service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

get_my_ip := $(shell hostname --all-ip-addresses | cut --delimiter=" " --fields=1)
export DASK_MONITORING_URL := tcp://dask-scheduler:8786
.PHONY: up-devel up-computational-devel down


.stack-devel.yml: .env
	../../scripts/docker/docker-compose-config.bash -e .env \
		docker-compose.yml \
		> $@

.stack-computational-devel.yml: .env
	../../scripts/docker/docker-compose-config.bash -e .env \
		docker-compose.yml \
		docker-compose-computational.yml \
		> $@

up-devel: .init-swarm .stack-devel.yml ## starts local test application
	@docker stack deploy --with-registry-auth --compose-file=.stack-devel.yml autoscaling

up-computational-devel: .init-swarm .stack-computational-devel.yml ## starts local test application in computational mode
	# DASK_MONITORING_URL set to $(DASK_MONITORING_URL)
	@docker stack deploy --with-registry-auth --compose-file=.stack-computational-devel.yml comp-autoscaling

down: .env ## stops local test app dependencies (running bare metal against AWS)
	-@docker stack rm comp-autoscaling-manual-testing
	-@docker stack rm autoscaling-manual-testing


SWARM_HOSTS = $(shell docker node ls --format="{{.Hostname}}" 2>$(if $(IS_WIN),NUL,/dev/null))
.PHONY: .init-swarm
.init-swarm:
	# Ensures swarm is initialized
	$(if $(SWARM_HOSTS),,docker swarm init --advertise-addr=$(get_my_ip))

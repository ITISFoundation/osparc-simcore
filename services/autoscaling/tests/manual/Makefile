include ../../../../scripts/common.Makefile
include ../../../../scripts/common-service.Makefile


.PHONY: up-devel up-computational-devel down


.stack-devel.yml: .env
	../../../../scripts/docker/docker-stack-config.bash -e .env \
		docker-compose.yml \
		> $@

.stack-computational-devel.yml: .env
	../../../../scripts/docker/docker-stack-config.bash -e .env \
		docker-compose.yml \
		docker-compose-computational.yml \
		> $@

up-devel: .init-swarm .stack-devel.yml ## starts local test application
	@docker stack deploy --with-registry-auth --compose-file=.stack-devel.yml autoscaling
	# to follow logs of autoscaling, run
	# docker service logs --follow autoscaling_autoscaling

up-computational-devel: .init-swarm .stack-computational-devel.yml ## starts local test application in computational mode
	# DASK_MONITORING_URL set to $(DASK_MONITORING_URL)
	@docker stack deploy --with-registry-auth --compose-file=.stack-computational-devel.yml comp-autoscaling
	# to follow logs of autoscaling, run
	# docker service logs --follow comp-autoscaling_autoscaling

down: .env ## stops local test app dependencies (running bare metal against AWS)
	# remove stacks
	-@docker stack rm comp-autoscaling
	-@docker stack rm autoscaling
	# remove stack files
	-rm -rf .stack-devel.yml
	-rm -rf .stack-computational-devel.yml


SWARM_HOSTS = $(shell docker node ls --format="{{.Hostname}}" 2>$(if $(IS_WIN),NUL,/dev/null))
.PHONY: .init-swarm
.init-swarm:
	# Ensures swarm is initialized (careful we use a default pool of 172.20.0.0/14. Ensure you do not use private IPs in that range!)
	$(if $(SWARM_HOSTS),,docker swarm init --advertise-addr=$(get_my_ip) --default-addr-pool 172.20.0.0/14)

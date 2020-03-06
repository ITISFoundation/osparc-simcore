


.PHONY: up
up:
	docker swarm init
	docker-compose -f docker-compose.yml -f docker-compose-ops.yml config > docker-compose.ignore.yml
	docker stack deploy -c docker-compose.ignore.yml services

.PHONY: down
down:
	docker swarm leave --force

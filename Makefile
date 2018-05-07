# Pipelines Project Make File
# author: Sylvain Anderegg

rebuild:
	docker-compose -f services/docker-compose.yml build --no-cache

build:
	docker-compose -f services/docker-compose.yml build

start-swarm:
	docker swarm init
	docker-compose -f services/docker-compose.yml -f services/docker-compose.deploy.yml up

stop-swarm:
	docker-compose -f services/docker-compose.yml -f services/docker-compose.deploy.yml down
	docker swarm leave -f

start:
	docker-compose -f services/docker-compose.yml up

stop:
	docker-compose -f services/docker-compose.yml down

demo: start

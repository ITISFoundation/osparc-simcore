# Pipelines Project Make File
# author: Sylvain Anderegg

rebuild:
	docker-compose -f services/docker-compose.yml build --no-cache

build-dev:
	docker-compose -f services/docker-compose.yml -f services/docker-compose.dev.yml build --no-cache

build:
	docker-compose -f services/docker-compose.yml build

build-dev:
	docker-compose -f services/docker-compose.yml -f services/docker-compose.dev.yml build

demo:
	docker swarm init
	docker-compose -f services/docker-compose.yml up

start:
	docker swarm init
	docker-compose -f services/docker-compose.yml up

stop:
	docker-compose -f services/docker-compose.yml down
	docker swarm leave -f

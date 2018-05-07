# author: Sylvain Anderegg

rebuild:
	docker-compose -f services/docker-compose.yml build --no-cache

build:
	docker-compose -f services/docker-compose.yml build

deploy_up:
	docker swarm init
	docker-compose -f services/docker-compose.yml -f services/docker-compose.deploy.yml up

deploy_down:
	docker-compose -f services/docker-compose.yml -f services/docker-compose.deploy.yml down
	docker swarm leave -f

start:
	docker-compose -f services/docker-compose.yml up

stop:
	docker-compose -f services/docker-compose.yml down

demo: start

# Pipelines Project Make File
# author: Sylvain Anderegg

demo:
	docker swarm init
	docker-compose -f services/docker-compose.yml up

start: 
	docker swarm init
	docker-compose -f services/docker-compose.yml up

stop: 
	docker-compose -f services/docker-compose.yml down
	docker swarm leave -f
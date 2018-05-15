# author: Elliott Zastrow

# note: 'up' requires that swarm is already initialized,  will not stop swarm on 'down'

build:
	docker-compose -f docker-compose.yml build

rebuild:
	docker-compose -f docker-compose.yml build --no-cache

up:
	/bin/bash -c "ak=$$(pwgen -sB 20 1); docker secret create access_key $${ak}; echo $${ak}"
	/bin/bash -c "sk=$$(pwgen -sB 32 1); docker secret create secret_key $${sk}; echo $${sk}"
	docker stack deploy --compose-file=docker-compose.yml minio_stack

down:
	docker stack rm minio_stack


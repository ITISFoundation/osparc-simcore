build:
	docker-compose -f docker-compose.yml build

rebuild:
	docker-compose -f docker-compose.yml build --no-cache

up:
	docker-compose -f docker-compose.yml up

down:
	docker-compose -f docker-compose.yml down

devel-build:
	docker-compose -f docker-compose.yml -f docker-compose.devel.yml build

devel-rebuild:
	docker-compose -f docker-compose.yml -f docker-compose.devel.yml build --no-cache

devel-up:
	docker-compose -f docker-compose.yml -f docker-compose.devel.yml up -d

devel-down:
	docker-compose -f docker-compose.yml -f docker-compose.devel.yml down
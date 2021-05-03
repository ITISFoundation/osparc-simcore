#
# Targets for DEVELOPMENT for performance test web-api
#
include ../../scripts/common.Makefile

.PHONY: requirements
requirements: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)

.PHONY: build
build:
	docker buildx build --tag local/locust:latest .

.PHONY: up
up: build
	@export TARGET=$(target); \
	docker-compose --file docker-compose.yml up

down:
	docker-compose --file docker-compose.yml down

.PHONY: install
install-dev: _check_venv_active  ## installs dependencies
	# installing requirements
	pip-sync requirements/dev.txt

locusfile=$(if $(target),$(target),locusfile.py)

.PHONY: start
start: _check_venv_active .env  ## starts locust, a scriptable and scalable performance testing tool
	# Open http://localhost:8089/
	locust --locustfile $(locusfile) --host http://127.0.0.1:9081  --users 3 --spawn-rate 1


.PHONY: list
list: _check_venv_active
	locust --list

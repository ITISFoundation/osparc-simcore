#
# Targets for DEVELOPMENT for performance test web-api
#
include ../../scripts/common.Makefile

LOCUST_VERSION=2.29.1
export LOCUST_VERSION

ENV_FILE=$(shell pwd)/.env
export ENV_FILE

# UTILS
get_my_ip := $(shell (hostname --all-ip-addresses || hostname -i) 2>/dev/null | cut --delimiter=" " --fields=1)

# Check that given variables are set and all have non-empty values,
# die with an error otherwise.
#
# Params:
#   1. Variable name(s) to test.
#   2. (optional) Error message to print.
check_defined = \
    $(strip $(foreach 1,$1, \
        $(call __check_defined,$1,$(strip $(value 2)))))
__check_defined = \
    $(if $(value $1),, \
      $(error Undefined $1$(if $2, ($2))))


.PHONY: build
build: ## builds distributed osparc locust docker image
	docker buildx build --load --build-arg LOCUST_VERSION=$(LOCUST_VERSION) --tag itisfoundation/locust:$(LOCUST_VERSION) --tag local/locust:latest .

.PHONY: push
push:
	docker push itisfoundation/locust:$(LOCUST_VERSION)

.PHONY: down
down: ## stops and removes osparc locust containers
	docker compose --file docker-compose.yml down

.PHONY: test
test: ## runs osparc locust. Locust and test configuration are specified in ENV_FILE
	if [ ! -f $${ENV_FILE} ]; then echo "You must generate a .env file before running tests!!! See the README..." && exit 1; fi; \
	docker compose --file docker-compose.yml up --scale worker=4 --exit-code-from=master

.PHONY: install-ci install-dev install

install-dev: install
install-ci: install

install: _check_venv_active ## install python tools
	@uv pip install -r requirements.txt


.PHONY: dashboards-up dashboards-down

dashboards-up: ## Create Grafana dashboard for inspecting locust results. See dashboard on localhost:3000
	locust-compose up --exit-code-from=grafana

dashboards-down:
	locust-compose down

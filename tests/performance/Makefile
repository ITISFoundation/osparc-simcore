#
# Targets for DEVELOPMENT for performance test web-api
#
include ../../scripts/common.Makefile

LOCUST_VERSION=2.5.1
export LOCUST_VERSION

# UTILS
get_my_ip := $(shell hostname --all-ip-addresses | cut --delimiter=" " --fields=1)

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

.PHONY: up down run
up: ## runs distributed osparc locust using target=locust_test_file.py, optional host can be set
	@$(call check_defined, target, please define target file when calling $@ - e.g. ```make $@ target=MY_LOCUST_FILE.py```)
	@export LOCUST_FILE=$(target); \
	export TARGET_URL=$(if $(host),$(host),"http://$(get_my_ip):9081"); \
	docker compose --file docker-compose.yml up --scale worker=4

down: ## stops and removes osparc locust containers
	docker compose --file docker-compose.yml down

.PHONY: test
test: ## runs osparc locust with target=locust_test_file.py in headless mode for a minute. Will fail if 5% more fail requests or average response time is above 50ms, optional host can be set
	@$(call check_defined, target, please define target file when calling $@ - e.g. ```make $@ target=MY_LOCUST_FILE.py```)
	@export LOCUST_FILE=$(target); \
	export TARGET_URL=$(if $(host),$(host),"http://$(get_my_ip):9081"); \
	export LOCUST_OPTIONS="--headless --print-stats --users=100 --spawn-rate=20 --run-time=1m --check-fail-ratio=0.01 --check-avg-response-time=$(if $(resp_time),$(resp_time),200)"; \
	docker compose --file docker-compose.yml up --scale worker=4 --exit-code-from=master

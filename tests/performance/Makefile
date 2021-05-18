#
# Targets for DEVELOPMENT for performance test web-api
#
include ../../scripts/common.Makefile


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

.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)

.PHONY: build
build:
	docker buildx build --tag local/locust:latest .

.PHONY: up down run
up:
	@$(call check_defined, target, please define target file when calling $@ - e.g. ```make $@ target=MY_LOCUST_FILE.py```)
	@export TARGET=$(target); export HOST=$(get_my_ip); \
	docker-compose --file docker-compose.yml up --scale worker=4

down:
	docker-compose --file docker-compose.yml down

.PHONY: test
test:
	@$(call check_defined, target, please define target file when calling $@ - e.g. ```make $@ target=MY_LOCUST_FILE.py```)
	@export TARGET=$(target); \
	export HOST=$(get_my_ip); \
	export LOCUST_OPTIONS="--headless --print-stats --users=100 --spawn-rate=20 --run-time=2m --check-fail-ratio=0.05 --check-avg-response-time=50"; \
	docker-compose --file docker-compose.yml up --scale worker=4

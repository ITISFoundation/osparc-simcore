#
# DEVELOPMENT recipes for Auto scaling service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)


.PHONY: test-local
up-devel: .env ## starts local test application (running bare metal against AWS)
	# setting up dependencies
	@docker compose up

down: .env ## stops local test app dependencies (running bare metal against AWS)
	-@docker compose down

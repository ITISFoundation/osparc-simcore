#
# DEVELOPMENT recipes for Auto scaling service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)


show-local-settings: .env ## shows local test settings (running bare metal against AWS)
	# setting up dependencies
	@docker compose up --detach
	@set -o allexport \
	&& source $(CURDIR)/.env \
	&& set +o allexport \
	&& simcore-service-clusters-keeper settings

.PHONY: test-local
up-local: .env ## starts local test application (running bare metal against AWS)
	# setting up dependencies
	@docker compose up --detach
	@set -o allexport \
	&& source $(CURDIR)/.env \
	&& set +o allexport \
	&& uvicorn simcore_service_clusters_keeper.main:the_app \
	--host 0.0.0.0 \
	--reload

down-local: .env ## stops local test app dependencies (running bare metal against AWS)
	-@docker compose down

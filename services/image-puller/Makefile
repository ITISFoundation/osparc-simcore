include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile

APP_NAME := $(notdir $(CURDIR))

.DEFAULT_GOAL := help


.env: .env-devel ## creates .env file from defaults in .env-devel
	$(if $(wildcard $@), \
	@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
	@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)

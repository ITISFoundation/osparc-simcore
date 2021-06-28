#
# DEVELOPMENT recipes for Workflows manager service
#
include ../../scripts/common.Makefile
include ../../scripts/common-service.Makefile


TEMP_DIR := $(shell mktemp -d -t dask-docker-XXX)

PHONY: build-official-dask
#
# NOTE:  At this moment, this does not seem to work https://docs.docker.com/engine/reference/commandline/build/
# export DOCKER_BUILDKIT=0; docker build --tag local/dask:master https://github.com/dask/dask-docker.git#:base
#
build-official-dask: # builds official dask container from master branch repo
	git clone --depth 1 https://github.com/dask/dask-docker.git ${TEMP_DIR} && \
	docker build --tag local/dask:master ${TEMP_DIR}/base && \
	rm -rf ${TEMP_DIR}

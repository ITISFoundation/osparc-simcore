#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
# https://github.com/GoogleChrome/puppeteer/blob/master/docs/troubleshooting.md#running-puppeteer-on-travis-ci
set -euo pipefail
IFS=$'\n\t'

# in case it's a Pull request, the env are never available, default to itisfoundation to get a maybe not too old version for caching
DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG

SWARM_STACK_NAME=e2e_test_stack
export SWARM_STACK_NAME

install() {
    echo "--------------- installing psql client..."
    /bin/bash -c 'sudo apt install -y postgresql-client'
    echo "--------------- getting simcore docker images..."
    make pull-version || ( (make pull-cache || true) && make build-x tag-version)
    make info-images

    # configure simcore for testing with a private registry
    bash tests/e2e/scripts/setup_env_insecure_registry.bash

    # start simcore and set log-level
    export LOG_LEVEL=WARNING; make up-version

    echo "-------------- installing test framework..."
    # create a python venv and activate
    make .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    bash ci/helpers/ensure_python_pip.bash
    pushd tests/e2e;
    make install
    echo "--------------- deploying the registry..."
    make registry-up
    echo "--------------- waiting for all services to be up..."
    make wait-for-services
    echo "--------------- transfering the images to the local registry..."
    make transfer-images-to-registry
    echo "--------------- injecting templates in postgres db..."
    make pg-db-tables
    make inject-templates-in-db
    popd
}

test() {
    pushd tests/e2e; make test; popd

}

recover_artifacts() {
    # all screenshots are in tests/e2e/screenshots if any

    # get docker logs.
    # WARNING: dumping long logs might take hours!!
    mkdir simcore_logs
    (docker service logs --timestamps --tail=300 --details simcore_webserver > simcore_logs/webserver.log 2>&1) || true
    (docker service logs --timestamps --tail=200 --details simcore_director > simcore_logs/director.log  2>&1) || true
    (docker service logs --timestamps --tail=200 --details simcore_storage > simcore_logs/storage.log  2>&1) || true
    (docker service logs --timestamps --tail=200 --details simcore_sidecar > simcore_logs/sidecar.log  2>&1) || true
    (docker service logs --timestamps --tail=200 --details simcore_catalog > simcore_logs/catalog.log  2>&1) || true
}

clean_up() {
    echo "--------------- listing services running..."
    docker service ls
    echo "--------------- listing images available..."
    docker images
    echo "--------------- switching off..."
    make leave
}

# Check if the function exists (bash specific)
if declare -f "$1" > /dev/null
then
  # call arguments verbatim
  "$@"
else
  # Show a helpful error
  echo "'$1' is not a known function name" >&2
  exit 1
fi

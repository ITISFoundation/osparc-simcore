#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
# https://github.com/GoogleChrome/puppeteer/blob/master/docs/troubleshooting.md#running-puppeteer-on-travis-ci
set -euo pipefail
IFS=$'\n\t'

# in case it's a Pull request, the env are never available, default to itisfoundation to get a maybe not too old version for caching
DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG

install() {
    echo "--------------- installing psql client..."
    /bin/bash -c 'sudo apt install -y postgresql-client'
    echo "--------------- getting simcore docker images..."
    make pull-version || ( (make pull-cache || true) && make build tag-version)
    make info-images
    # configure simcore for testing with a private registry
    bash tests/e2e/setup_env_insecure_registry
    # start simcore
    make up-version

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
    make inject-templates-in-db
    popd
}

test() {
    pushd tests/e2e; make test; popd

}

recover_artifacts() {
    # all screenshots are in tests/e2e/screenshots if any

    # get docker logs
    mkdir simcore_logs
    (docker service logs --timestamps simcore_webserver > simcore_logs/webserver.log) || true
    (docker service logs --timestamps simcore_director > simcore_logs/director.log ) || true
    (docker service logs --timestamps simcore_storage > simcore_logs/storage.log) || true
    (docker service logs --timestamps simcore_sidecar > simcore_logs/sidecar.log) || true
    (docker service logs --timestamps simcore_catalog > simcore_logs/catalog.log) || true
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

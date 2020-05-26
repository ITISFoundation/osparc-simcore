#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
# https://github.com/GoogleChrome/puppeteer/blob/master/docs/troubleshooting.md#running-puppeteer-on-travis-ci
set -euo pipefail
IFS=$'\n\t'

# in case it's a Pull request, the env are never available, default to itisfoundation to get a maybe not too old version for caching
DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG

if [[ ! -v DOCKER_REGISTRY ]]; then
    export DOCKER_REGISTRY="itisfoundation"
fi


before_install() {
    bash ci/travis/helpers/update-docker.bash
    bash ci/travis/helpers/install-docker-compose.bash
    bash ci/helpers/show_system_versions.bash
    sudo apt install -y postgresql-client
}

install() {
    echo "nothing to do here..."
}

before_script() {
    echo "--------------- getting simcore docker images..."
    make pull-version || ( (make pull-cache || true) && make build tag-version)
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

script() {
    pushd tests/e2e; make test; popd
}

after_success() {
    # ToDo: call coveralls
    make down
}

after_failure() {
    echo "--------------- logs of webserver..."
    docker service logs simcore_webserver
    echo "--------------- logs of sidecar..."
    docker service logs simcore_sidecar
    echo "--------------- logs of director..."
    docker service logs simcore_director
    echo "--------------- logs of storage..."
    docker service logs simcore_storage
    docker images
    make down
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

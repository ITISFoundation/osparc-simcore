#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
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
}

install() {
    bash ci/helpers/ensure_python_pip.bash
    pushd services/web/server; pip3 install -r requirements/ci.txt; popd;
}

before_script() {
    pip list -v
    make pull-version || ( (make pull-cache || true) && make build tag-version)
    make info-images
}

script() {
    pytest --cov=simcore_service_webserver --durations=10 --cov-append \
        --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
        -v -m "not travis" services/web/server/tests/integration
    # TODO: https://github.com/ITISFoundation/osparc-simcore/issues/560
    #pytest --cov=simcore_service_webserver -v services/web/server/tests/integration-proxy
}

after_success() {
    coveralls
}

after_failure() {
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

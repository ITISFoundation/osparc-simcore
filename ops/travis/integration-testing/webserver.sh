#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

# in case it's a Pull request, the env are never available, default to itisfoundation to get a maybe not too old version for caching
export DOCKER_IMAGE_TAG=$(exec ops/travis/helpers/build_docker_image_tag.sh)

before_install() {
    bash ops/travis/helpers/install_docker_compose.sh
    bash ops/travis/helpers/show_system_versions.sh
}

install() {
    pip install --upgrade pip wheel setuptools && pip3 --version
    pushd services/web/server/tests; pip3 install -r requirements.txt; popd
    pushd services/web/server/tests/integration; pip3 install -r requirements.txt; popd
}

before_script() {
    pip freeze
    make pull-cache || true
    make pull || make build
    docker images
}

script() {
    pytest --cov=simcore_service_webserver --cov-append -v services/web/server/tests/integration
    # TODO: https://github.com/ITISFoundation/osparc-simcore/issues/560
    #pytest --cov=simcore_service_webserver -v services/web/server/tests/integration-proxy
}

after_success() {
    coveralls
    codecov
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

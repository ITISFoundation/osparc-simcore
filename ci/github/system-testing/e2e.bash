#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
# https://github.com/GoogleChrome/puppeteer/blob/master/docs/troubleshooting.md#running-puppeteer-on-travis-ci
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

# in case it's a Pull request, the env are never available, default to itisfoundation to get a maybe not too old version for caching
DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG

install() {
  pushd tests/e2e
  make install-ci
  popd
}

build() {
  value=${1:-}
  if
    [ "$value" ] && [ "$value" == "pull" ]
  then
    make pull-version || true
  fi
  make build tag-version
  make info-images
}

test() {
  pushd tests/e2e
  make test
  popd
}

setup_images() {
  echo "--------------- preparing docker images..."
  make pull-version || (make build tag-version)
  make info-images

}

clean_up() {
  echo "--------------- listing services running..."
  docker service ls || true
  echo "--------------- listing service details..."
  # shellcheck disable=SC2046
  docker service ps --no-trunc $(docker service ls --quiet) || true
  echo "--------------- listing container details..."
  docker container ps -a
  echo "--------------- listing images available..."
  docker images
  echo "--------------- switching off..."
  pushd tests/e2e
  make clean-up
  popd
}

dump_docker_logs() {
  # get docker logs
  # NOTE: Timeout avoids issue with dumping logs that hang!
  mkdir --parents simcore_logs
  (timeout 30 docker service logs --timestamps --tail=300 --details "${SWARM_STACK_NAME:-test}"_webserver >simcore_logs/webserver.log 2>&1) || true
  # then the rest (alphabetically)
  (timeout 30 docker service logs --timestamps --tail=100 --details "${SWARM_STACK_NAME:-test}"_api-server >simcore_logs/api-server.log 2>&1) || true
  (timeout 30 docker service logs --timestamps --tail=200 --details "${SWARM_STACK_NAME:-test}"_catalog >simcore_logs/catalog.log 2>&1) || true
  (timeout 30 docker service logs --timestamps --tail=200 --details "${SWARM_STACK_NAME:-test}"_director >simcore_logs/director.log 2>&1) || true
  (timeout 30 docker service logs --timestamps --tail=200 --details "${SWARM_STACK_NAME:-test}"_director-v2 >simcore_logs/director-v2.log 2>&1) || true
  (timeout 30 docker service logs --timestamps --tail=200 --details "${SWARM_STACK_NAME:-test}"_sidecar >simcore_logs/sidecar.log 2>&1) || true
  (timeout 30 docker service logs --timestamps --tail=200 --details "${SWARM_STACK_NAME:-test}"_storage >simcore_logs/storage.log 2>&1) || true
  (timeout 30 docker service logs --timestamps --tail=200 --details "${SWARM_STACK_NAME:-test}"_migration >simcore_logs/migration.log 2>&1) || true
  (timeout 30 docker service logs --timestamps --tail=200 --details "${SWARM_STACK_NAME:-test}"_postgres >simcore_logs/postgres.log 2>&1) || true
}

# Check if the function exists (bash specific)
if declare -f "$1" >/dev/null; then
  # call arguments verbatim
  "$@"
else
  # Show a helpful error
  echo "'$1' is not a known function name" >&2
  exit 1
fi

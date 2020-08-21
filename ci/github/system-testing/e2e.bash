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

install_insecure_registry() {
  # Create .env and append extra variables
  if [[ -f .env ]]; then
    cp .env .env.bak
  fi

  make .env
  {
    # disable email verification
    echo WEBSERVER_LOGIN_REGISTRATION_INVITATION_REQUIRED=0
    echo WEBSERVER_LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=0
    # set max number of CPUs sidecar
    echo SERVICES_MAX_NANO_CPUS=2000000000
    # set up insecure internal registry
    echo REGISTRY_AUTH=False
    echo REGISTRY_SSL=False
    echo REGISTRY_URL=registry:5000
    # disable registry caching to ensure services are fetched
    echo DIRECTOR_REGISTRY_CACHING=False
    echo DIRECTOR_REGISTRY_CACHING_TTL=0
    # shorten time to sync services from director since registry comes later
    echo CATALOG_BACKGROUND_TASK_REST_TIME=1
  } >>.env

  # prepare insecure registry access for docker engine
  echo "------------------- adding host name to the insecure registry "
  if [[ -f /etc/hosts ]]; then
    cp /etc/hosts .hosts.bak
  fi
  sudo bash -c "echo '127.0.0.1 registry' >> /etc/hosts"

  echo "------------------- adding insecure registry into docker daemon "
  if [[ -f /etc/docker/daemon.json ]]; then
    cp /etc/docker/daemon.json .daemon.bak
  fi
  sudo bash -c "echo '{\"insecure-registries\": [\"registry:5000\"]}' >> /etc/docker/daemon.json"

  echo "------------------ restarting daemon [takes some time]"
  sudo service docker restart
}

uninstall_insecure_registry() {
  echo "------------------ reverting .env"
  if [[ -f .env.bak ]]; then
    mv .env.bak .env
  fi

  echo "------------------ reverting /etc/hosts"
  if [[ -f .hosts.bak ]]; then
    sudo mv .hosts.bak /etc/hosts
  fi

  if [[ -f .daemon.bak ]]; then
    echo "------------------ reverting /etc/docker/daemon.json"
    sudo mv .daemon.bak /etc/docker/daemon.json
    echo "------------------ restarting daemon [takes some time]"
    sudo service docker restart
  fi
}

setup_images() {
  echo "--------------- getting simcore docker images..."
  make pull-version || ( (make pull-cache || true) && make build-x tag-version)
  make info-images

  # configure simcore for testing with a private registry
  install_insecure_registry

  # start simcore and set log-level
  export LOG_LEVEL=WARNING
  make up-version
}

setup_environment() {

  echo "--------------- installing environment ..."
  /bin/bash -c 'sudo apt install -y postgresql-client'

  echo "-------------- installing test framework..."
  # create a python venv and activate
  make .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate

  bash ci/helpers/ensure_python_pip.bash
  pushd tests/e2e
  make install
  popd
}

setup_registry() {
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pushd tests/e2e
  echo "--------------- deploying the registry..."
  make registry-up
  echo "--------------- waiting for all services to be up..."
  make wait-for-services
  echo "--------------- transfering the images to the local registry..."
  make transfer-images-to-registry
  popd
}

setup_database() {
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pushd tests/e2e
  echo "--------------- injecting templates in postgres db..."

  # Checks that pg is up and running
  IMAGE_NAME="$(docker image ls --filter 'reference=postgres*' --format "{{.Repository}}:{{.Tag}}" | tail -1)"
  docker ps --filter "ancestor=$IMAGE_NAME"
  docker inspect "$(docker ps --filter "ancestor=$IMAGE_NAME" -q)"

  # Injects project template
  make inject-templates-in-db
  popd
}

install() {
  ## shortcut
  setup_images
  setup_environment
  setup_registry
  setup_database
}

test() {
  pushd tests/e2e
  make test
  popd

}

recover_artifacts() {
  # all screenshots are in tests/e2e/screenshots if any

  # get docker logs.
  # WARNING: dumping long logs might take hours!!
  mkdir simcore_logs
  (docker service logs --timestamps --tail=300 --details ${SWARM_STACK_NAME}_webserver >simcore_logs/webserver.log 2>&1) || true
  (docker service logs --timestamps --tail=200 --details ${SWARM_STACK_NAME}_director >simcore_logs/director.log 2>&1) || true
  (docker service logs --timestamps --tail=200 --details ${SWARM_STACK_NAME}_storage >simcore_logs/storage.log 2>&1) || true
  (docker service logs --timestamps --tail=200 --details ${SWARM_STACK_NAME}_sidecar >simcore_logs/sidecar.log 2>&1) || true
  (docker service logs --timestamps --tail=200 --details ${SWARM_STACK_NAME}_catalog >simcore_logs/catalog.log 2>&1) || true
}

clean_up() {
  echo "--------------- listing services running..."
  docker service ls
  echo "--------------- listing images available..."
  docker images
  echo "--------------- switching off..."
  make leave
  echo "--------------- uninstalling insecure registry"
  uninstall_insecure_registry
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

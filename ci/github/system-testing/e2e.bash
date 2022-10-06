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

test() {
  pushd tests/e2e
  make test
  popd
}

setup_images() {
  echo "--------------- preparing docker images..."
  # make pull-version || (make build tag-version)
  make info-images

}

clean_up() {
  echo "--------------- listing services running..."
  docker service ls
  echo "--------------- listing service details..."
  # shellcheck disable=SC2046
  docker service ps --no-trunc $(docker service ls --quiet)
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
  out_dir=tests/e2e/test_failures
  mkdir --parents "$out_dir"

  for service_id in $(docker service ls -q); do
    service_name=$(docker service inspect "$service_id" --format="{{.Spec.Name}}")
    echo "Dumping logs for $service_name"
    (timeout 30 docker service logs --timestamps --tail=400 --details "$service_id" >"$out_dir/$service_name.log" 2>&1) || true
  done
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

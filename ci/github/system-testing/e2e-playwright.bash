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
  make devenv
  make pull-externals
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd tests/e2e-playwright
  make install-ci-up-simcore
  popd
}

test() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd tests/e2e-playwright
  make test-sleepers
  make test-platform
  popd
}

dump_docker_logs() {
  # get docker logs
  # NOTE: Timeout avoids issue with dumping logs that hang!
  out_dir=tests/e2e-playwright/test_failures
  mkdir --parents "$out_dir"

  for service_id in $(docker service ls -q); do
    service_name=$(docker service inspect "$service_id" --format="{{.Spec.Name}}")
    echo "Dumping logs for $service_name"
    (timeout 30 docker service logs --timestamps --tail=500 --details "$service_id" >"$out_dir/$service_name.log" 2>&1) || true

    # dump service inspect
    service_dir="$out_dir/$service_name"
    mkdir --parents "$service_dir"
    docker service inspect "$service_id" >"$service_dir/service_inspect.json" 2>&1 || true

    # dump task inspects
    for task_id in $(docker service ps "$service_id" -q); do
      task_info=$(docker inspect "$task_id" --format="{{.Status.ContainerStatus.ContainerID}} {{index .Spec.ContainerSpec.Labels \"com.docker.swarm.task.name\"}}" 2>/dev/null || echo "")
      if [ -n "$task_info" ]; then
        container_id=$(echo "$task_info" | awk '{print $1}')
        task_name=$(echo "$task_info" | awk '{print $2}' | sed 's/.*\.//')
        # Fallback to task_id if task_name is empty
        if [ -z "$task_name" ]; then
          task_name="$task_id"
        fi
        if [ -n "$container_id" ]; then
          docker inspect "$container_id" >"$service_dir/container_${task_name}.json" 2>&1 || true
        fi
      fi
    done
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

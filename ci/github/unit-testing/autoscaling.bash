#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

install() {
  make devenv
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/autoscaling
  make install-ci
  popd
  uv pip list
}

TEST_01_FILES=(
  tests/unit/test_api_health.py
  tests/unit/test_core_settings.py
  tests/unit/test_main.py
  tests/unit/test_models.py
  tests/unit/test_modules_cluster_scaling_auto_scaling_task.py
  tests/unit/test_modules_cluster_scaling_dynamic.py
  tests/unit/test_modules_cluster_scaling_warm_buffer_machine_core.py
  tests/unit/test_modules_instrumentation_utils.py
  tests/unit/test_modules_rabbitmq.py
  tests/unit/test_modules_redis.py
  tests/unit/test_modules_ssm.py
  tests/unit/test_utils_capacity_distribution.py
  tests/unit/test_utils_rabbitmq.py
)

test_01() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/autoscaling
  # NOTE: "${TEST_01_FILES[*]}" would join with IFS (set to $'\n\t' above), not a
  # space, so printf is used instead to build a space-separated argument list.
  local test_01_targets
  test_01_targets="$(printf '%s ' "${TEST_01_FILES[@]}")"
  # NOTE: target must be set explicitly to the selected test files, otherwise
  # test-ci-unit defaults it to the whole tests/unit folder (running ALL tests)
  make test-ci-unit target="${test_01_targets}"
  popd
}

test_02() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/autoscaling
  local ignore_args=""
  local test_file
  for test_file in "${TEST_01_FILES[@]}"; do
    ignore_args+="--ignore=${test_file} "
  done
  # runs everything in tests/unit except what test_01 already covers
  make test-ci-unit pytest-parameters="${ignore_args}"
  popd
}

test() {
  test_01
  test_02
}

typecheck() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  uv pip install mypy
  pushd services/autoscaling
  make mypy
  popd
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

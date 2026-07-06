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
  pushd services/storage
  make install-ci
  popd
  uv pip list
}

_test_shard() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/storage
  local shard_args=""
  local test_file
  for test_file in "$@"; do
    shard_args+="${test_file} "
  done
  make test-ci-unit pytest-parameters="--disk-usage ${shard_args}"
  popd
}

TEST_01_FILES=(
  tests/unit/test__legacy_storage_sdk_compatibility.py
  tests/unit/test_async_jobs_handlers_paths.py
  tests/unit/test_cli.py
  tests/unit/test_core_settings.py
  tests/unit/test_handlers_datcore.py
  tests/unit/test_handlers_datasets.py
  tests/unit/test_handlers_health.py
  tests/unit/test_handlers_locations.py
  tests/unit/test_handlers_paths.py
  tests/unit/test_models.py
  tests/unit/test_modules_rabbitmq.py
  tests/unit/test_resources.py
  tests/unit/test_simcore_s3_dsm_utils.py
  tests/unit/test_utils.py
  tests/unit/test_utils_handlers.py
)

_test_remaining_shard() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/storage
  local all_tests test_01_args pytest_args
  mapfile -t all_tests < <(find tests/unit -type f -name 'test*.py' | sort)
  test_01_args=()
  pytest_args=""
  for test_file in "${TEST_01_FILES[@]}"; do
    test_01_args+=("--ignore=${test_file}")
  done
  for test_file in "${test_01_args[@]}" "${all_tests[@]}"; do
    pytest_args+="${test_file} "
  done
  make test-ci-unit pytest-parameters="--disk-usage ${pytest_args}"
  popd
}

test_01() {
  _test_shard \
    "${TEST_01_FILES[@]}"
}

test_02() {
  _test_remaining_shard
}

test() {
  test_01
  test_02
}

typecheck() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  uv pip install mypy
  pushd services/storage
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

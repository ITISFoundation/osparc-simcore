#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

install() {
  bash ci/helpers/ensure_python_pip.bash
  pushd packages/dask-task-models-library
  pip3 install \
      --requirement requirements/ci.txt \
      --requirement requirements/_tools.txt
  popd
  pip list --verbose
}

codestyle() {
  pushd packages/dask-task-models-library
  make codestyle-ci
  popd
}

test() {
  pytest \
    --color=yes \
    --cov-append \
    --cov-config=.coveragerc \
    --cov-report=term-missing \
    --cov-report=xml \
    --cov=dask_task_models_library \
    --durations=10 \
    --verbose \
    packages/dask-task-models-library/tests
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

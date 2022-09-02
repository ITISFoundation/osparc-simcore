#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

install() {
  # Replaces 'bash ci/helpers/ensure_python_pip.bash'

  echo "INFO:" "$(python --version)" "@" "$(command -v python)"

  # installs pip if not in place
  python -m ensurepip

  echo "INFO:" "$(pip --version)" "@" "$(command -v pip)"
  make devenv
  # shellcheck source=/dev/null
  source .venv/bin/activate
  # NOTE: pip<22.0 for python 3.6
  pip3 install --upgrade \
    pip~=21.0 \
    wheel \
    setuptools
  pushd services/director
  make install-ci
  popd
  .venv/bin/pip list --verbose
}

test() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/director
  make test-ci-unit
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

#!/bin/bash
#

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

install() {
  bash ci/helpers/ensure_python_pip.bash
  pushd tests/environment-setup
  pip3 install -r requirements/ci.txt
  popd
  make .env
}

test() {
  pytest --color=yes -v tests/environment-setup --log-level=DEBUG --asyncio-mode=auto
}

clean_up() {
  ls -la tests/environment-setup
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

#!/bin/bash
#
#  Installs pylint using same version as servicelib
#

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

CURDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

REQUIREMENTS=packages/service-library/requirements/_tools.txt
PYLINT_VERSION="$(grep pylint== $REQUIREMENTS | awk '{print $1}')"
uv pip install "$PYLINT_VERSION"

# Minimal packages to pass linter
echo "$CURDIR/requirements/requirements.txt"
uv pip install -r "$CURDIR/requirements/requirements.txt"

echo "INFO:" "$(pylint --version)" "@" "$(command -v pylint)"

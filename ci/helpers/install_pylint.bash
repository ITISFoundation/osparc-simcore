#!/bin/bash
#
#  Installs pylint using same version as servicelib
#

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

CURDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"


REQUIREMENTS=packages/service-library/requirements/_test.txt
PYLINT_VERSION="$(grep pylint== $REQUIREMENTS | awk '{print $1}')"
pip3 install "$PYLINT_VERSION"

# Minimal packages to pass linter
pip install -r $CURDIR/requirements.txt


echo "INFO:" "$(pylint --version)" "@" "$(command -v pylint)"

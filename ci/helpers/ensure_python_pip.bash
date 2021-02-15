#!/bin/bash
#
#  Bootstrapping the pip installer
#
# SEE https://docs.python.org/3/library/ensurepip.html
#
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

# Pin pip version to a compatible release https://www.python.org/dev/peps/pep-0440/#compatible-release
PIP_VERSION=21.0.1

echo "INFO:" "$(python --version)" "@" "$(command -v python)"

# installs pip if not in place
python -m ensurepip

echo "INFO:" "$(pip --version)" "@" "$(command -v pip)"

pip3 install --upgrade \
  pip~=$PIP_VERSION \
  wheel \
  setuptools

#!/bin/bash
#
#  Installs the latest version of 7zip plugin
#

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

apt-get install p7zip-full

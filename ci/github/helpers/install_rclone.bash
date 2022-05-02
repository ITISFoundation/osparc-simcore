#!/bin/bash
#
#  Installs the latest version of rclone plugin
#

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'


R_CLONE_VERSION="1.58.0"
curl -sLO "https://downloads.rclone.org/v${R_CLONE_VERSION}/rclone-v${R_CLONE_VERSION}-linux-amd64.deb"
dpkg -i "rclone-v${R_CLONE_VERSION}-linux-amd64.deb"
rm "rclone-v${R_CLONE_VERSION}-linux-amd64.deb"
rclone --version

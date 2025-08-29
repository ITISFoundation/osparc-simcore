#!/bin/bash
#
#  Installs the latest version of rclone plugin
#

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

R_CLONE_VERSION="1.70.3"
TARGETARCH="${TARGETARCH:-amd64}"

echo "platform ${TARGETARCH}"

curl --silent --location --remote-name "https://downloads.rclone.org/v${R_CLONE_VERSION}/rclone-v${R_CLONE_VERSION}-linux-${TARGETARCH}.deb"
dpkg --install "rclone-v${R_CLONE_VERSION}-linux-${TARGETARCH}.deb"
rm "rclone-v${R_CLONE_VERSION}-linux-${TARGETARCH}.deb"
rclone --version

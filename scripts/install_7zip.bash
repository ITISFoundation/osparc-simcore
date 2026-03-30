#!/bin/bash
#
#  Installs 7zip
#

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

TARGETARCH="${TARGETARCH:-amd64}"

case "${TARGETARCH}" in \
  "amd64") ARCH="x64" ;; \
  "arm64") ARCH="arm64" ;; \
  *) echo "Unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
esac

SEVEN_ZIP_VERSION="2409"

echo "create install dir"
rm -rf /tmp/7zip
mkdir -p /tmp/7zip
cd /tmp/7zip

curl -LO https://www.7-zip.org/a/7z${SEVEN_ZIP_VERSION}-linux-${ARCH}.tar.xz
tar -xvf 7z${SEVEN_ZIP_VERSION}-linux-${ARCH}.tar.xz
cp 7zz /usr/bin/7z

echo "remove install dir"
rm -rf /tmp/7zip

echo "test installation"
7z --help

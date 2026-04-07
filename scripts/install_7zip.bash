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

# Latest versions available at https://www.7-zip.org/download.html
# GitHub releases: https://github.com/ip7z/7zip/releases
SEVEN_ZIP_VERSION="2600"
SEVEN_ZIP_VERSION_DOT="${SEVEN_ZIP_VERSION:0:2}.${SEVEN_ZIP_VERSION:2}"

echo "create install dir"
rm -rf /tmp/7zip
mkdir -p /tmp/7zip
cd /tmp/7zip

URL="https://github.com/ip7z/7zip/releases/download/${SEVEN_ZIP_VERSION_DOT}/7z${SEVEN_ZIP_VERSION}-linux-${ARCH}.tar.xz"

echo "Downloading from: ${URL}"
curl -LO \
  --retry 5 \
  --retry-delay 2 \
  --retry-max-time 60 \
  --retry-all-errors \
  "${URL}"
tar -xvf 7z${SEVEN_ZIP_VERSION}-linux-${ARCH}.tar.xz
cp 7zz /usr/bin/7z

echo "remove install dir"
rm -rf /tmp/7zip

echo "test installation"
7z --help

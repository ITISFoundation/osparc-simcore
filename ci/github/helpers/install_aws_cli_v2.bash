#!/bin/bash
#
#  Installs the latest version of AWS CLI V2
#

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

AWS_CLI_VERSION="2.11.11"
ARCH="x86_64"

curl "https://awscli.amazonaws.com/awscli-exe-linux-${ARCH}-${AWS_CLI_VERSION}.zip" --output "awscliv2.zip" &&
  apt-get update &&
  apt-get install -y unzip &&
  unzip awscliv2.zip &&
  ./aws/install --update &&
  apt-get remove --purge -y unzip &&
  rm awscliv2.zip &&
  rm -rf awscliv2

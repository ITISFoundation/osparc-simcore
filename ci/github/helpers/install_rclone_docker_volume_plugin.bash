#!/bin/bash
#
#  Installs the latest version of rclone plugin
#

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'


# Installation instructions from https://rclone.org/docker/

apt-get -y install fuse=2.9.9-3
mkdir --parents /var/lib/docker-plugins/rclone/config
mkdir --parents /var/lib/docker-plugins/rclone/cache
docker plugin install rclone/docker-volume-rclone:amd64-1.57.0 args="-v" --alias rclone --grant-all-permissions
docker plugin list
docker plugin inspect rclone

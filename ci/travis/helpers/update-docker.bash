#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt-get update
sudo apt-cache madison docker-ce
sudo apt-get -V -y -o Dpkg::Options::="--force-confnew" install docker-ce=${DOCKER_VERSION}
# fix for using buildkit
# echo ----------------------------- before modifications... ----------------------------
# cat /etc/docker/daemon.json
# echo ----------------------------- after modifications... ----------------------------
sudo echo "{}" > /etc/docker/daemon.json
# cat /etc/docker/daemon.json
sudo systemctl restart docker

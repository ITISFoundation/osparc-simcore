#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

# when changing the DOCKER_COMPOSE_VERSION please compute the sha256sum on an ubuntu box (macOS has different checksum)
DOCKER_COMPOSE_VERSION="1.25.3"
DOCKER_COMPOSE_SHA256SUM="b3835d30f66bd3b926511974138923713a253d634315479b9aa3166c0050da98"
curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# https://superuser.com/a/1465221
echo "$DOCKER_COMPOSE_SHA256SUM  /usr/local/bin/docker-compose" | sha256sum -c
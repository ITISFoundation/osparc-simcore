#!/bin/bash
# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

# when changing the DOCKER_COMPOSE_VERSION please compute the sha256sum on an ubuntu box (macOS has different checksum)
DOCKER_COMPOSE_VERSION="1.26.2"
DOCKER_COMPOSE_SHA256SUM="13e50875393decdb047993c3c0192b0a3825613e6dfc0fa271efed4f5dbdd6eb"
curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# https://superuser.com/a/1465221
echo "$DOCKER_COMPOSE_SHA256SUM  /usr/local/bin/docker-compose" | sha256sum -c

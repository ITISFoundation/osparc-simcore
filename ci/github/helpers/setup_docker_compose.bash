#!/bin/bash
# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

# when changing the DOCKER_COMPOSE_VERSION please compute the sha256sum on an ubuntu box (macOS has different checksum)
DOCKER_COMPOSE_VERSION="$1"
# Check for sha256 file in Asset section on https://github.com/docker/compose/releases
DOCKER_COMPOSE_SHA256SUM="$2"
DOCKER_COMPOSE_BIN=/usr/local/bin/docker-compose
curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o $DOCKER_COMPOSE_BIN
chmod +x $DOCKER_COMPOSE_BIN

# checks it runs
$DOCKER_COMPOSE_BIN --version

# location
where=$(command -v which docker-compose)
[ "$where" != "$DOCKER_COMPOSE_BIN" ] && echo "WARNING: docker-compose already pre-sintalled in $where "


# To create new DOCKER_COMPOSE_SHA256SUM = sha256sum ${DOCKER_COMPOSE_BIN}
# SEE https://superuser.com/a/1465221
echo "$DOCKER_COMPOSE_SHA256SUM  $DOCKER_COMPOSE_BIN" | sha256sum --check

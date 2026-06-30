#!/usr/bin/env bash
# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

repo_root="$(git rev-parse --show-toplevel)"

# shellcheck source=/dev/null
source "$repo_root/scripts/helpers/logger.bash"

# check script needed variables
if [ ! -v DOCKER_REGISTRY ] || [ ! -v DOCKER_IMAGE_TAG ]; then
    error_exit "$LINENO" "incorrect use of script. DOCKER_REGISTRY and/or DOCKER_IMAGE_TAG not defined!"
fi

if [ -z "${DOCKER_REGISTRY:-}" ] || [ -z "${DOCKER_IMAGE_TAG:-}" ]; then
    error_exit "$LINENO" "incorrect use of script. DOCKER_REGISTRY/DOCKER_IMAGE_TAG must be non-empty!"
fi

cd "$repo_root"

services="$(docker compose --file services/docker-compose-deploy.yml config --services)"
readonly services

# fuses the per-architecture registry images '<tag>-amd64' and '<tag>-arm64'
# into a single multi-arch manifest '<tag>' (registry-side, no layer movement)
for service in ${services}; do
    target_image="${DOCKER_REGISTRY}/${service}:${DOCKER_IMAGE_TAG}"
    log_info "fusing ${target_image}-amd64 + ${target_image}-arm64 -> ${target_image}"
    docker buildx imagetools create \
        --tag "${target_image}" \
        "${target_image}-amd64" \
        "${target_image}-arm64"
done

log_info "complete!"

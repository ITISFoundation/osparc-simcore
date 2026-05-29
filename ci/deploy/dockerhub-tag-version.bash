#!/usr/bin/env bash
# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"

# shellcheck source=/dev/null
source "$repo_root/scripts/helpers/logger.bash"

# check script needed variables
if [ ! -v FROM_DOCKER_TAG_PREFIX ] || [ ! -v TO_DOCKER_TAG_PREFIX ] || [ ! -v GIT_TAG ]; then
    error_exit "$LINENO" "incorrect use of script. FROM_DOCKER_TAG_PREFIX/TO_DOCKER_TAG_PREFIX (e.g. master-github, staging-github), and/or GIT_TAG not defined!"
fi

cd "$repo_root"

log_info "logging in dockerhub..."
bash ci/helpers/dockerhub_login.bash

log_info "finding the source image tag in the registry..."
export ORG="${DOCKER_REGISTRY}"
export REPO="webserver"
# FROM_DOCKER_TAG_PREFIX-DATE.GIT_SHA
export TAG_PATTERN="^${FROM_DOCKER_TAG_PREFIX}-.+\..+"
source_tag="$(./ci/helpers/find_docker_image_tag_from_git_sha.bash | awk 'END{print}')" || exit $?
log_info "found source image tag ${source_tag}"

promote_registry_tag() {
    local source_image="$1"
    local destination_image="$2"

    log_info "promoting ${source_image} -> ${destination_image}"
    docker buildx imagetools create --tag "${destination_image}" "${source_image}"
}

services="$(docker compose --file services/docker-compose-deploy.yml config --services)"
readonly git_commit_sha="$(git show-ref -s "${GIT_TAG}")"
versioned_image_tag="${TO_DOCKER_TAG_PREFIX}-${GIT_TAG}-$(date --utc +"%Y-%m-%d--%H-%M").${git_commit_sha}"
latest_image_tag="${TO_DOCKER_TAG_PREFIX}-latest"

for service in ${services}; do
    source_image="${DOCKER_REGISTRY}/${service}:${source_tag}"

    promote_registry_tag "${source_image}" "${DOCKER_REGISTRY}/${service}:${versioned_image_tag}"
done

for service in ${services}; do
    source_image="${DOCKER_REGISTRY}/${service}:${source_tag}"

    promote_registry_tag "${source_image}" "${DOCKER_REGISTRY}/${service}:${latest_image_tag}"
done

for service in ${services}; do
    source_image="${DOCKER_REGISTRY}/${service}:${source_tag}"

    promote_registry_tag "${source_image}" "${DOCKER_REGISTRY}/${service}:${GIT_TAG}"
done

log_info "complete!"

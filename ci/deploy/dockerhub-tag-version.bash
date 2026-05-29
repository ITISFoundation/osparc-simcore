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

if [ -z "${FROM_DOCKER_TAG_PREFIX:-}" ] || [ -z "${TO_DOCKER_TAG_PREFIX:-}" ] || [ -z "${GIT_TAG:-}" ]; then
    error_exit "$LINENO" "incorrect use of script. FROM_DOCKER_TAG_PREFIX/TO_DOCKER_TAG_PREFIX/GIT_TAG must be non-empty!"
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
readonly source_tag
log_info "found source image tag ${source_tag}"

services="$(docker compose --file services/docker-compose-deploy.yml config --services)"
readonly services
git_commit_sha="$(git show-ref -s "${GIT_TAG}")" || exit $?
readonly git_commit_sha
versioned_image_tag="${TO_DOCKER_TAG_PREFIX}-${GIT_TAG}-$(date --utc +"%Y-%m-%d--%H-%M").${git_commit_sha}"
readonly versioned_image_tag
latest_image_tag="${TO_DOCKER_TAG_PREFIX}-latest"
readonly latest_image_tag

for service in ${services}; do
    source_image="${DOCKER_REGISTRY}/${service}:${source_tag}"
    service_versioned_tag="${DOCKER_REGISTRY}/${service}:${versioned_image_tag}"
    service_latest_tag="${DOCKER_REGISTRY}/${service}:${latest_image_tag}"
    service_git_tag="${DOCKER_REGISTRY}/${service}:${GIT_TAG}"

    log_info "promoting ${source_image} -> ${service_versioned_tag} ${service_latest_tag} ${service_git_tag}"
    docker buildx imagetools create \
        --tag "${service_versioned_tag}" \
        --tag "${service_latest_tag}" \
        --tag "${service_git_tag}" \
        "${source_image}"
done

log_info "complete!"

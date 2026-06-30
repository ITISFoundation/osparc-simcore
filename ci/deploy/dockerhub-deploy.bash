#!/usr/bin/env bash
# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

my_dir="$(dirname "$0")"
# shellcheck source=/dev/null
source "$my_dir/../../scripts/helpers/logger.bash"


# check script needed variables
if [ ! -v TAG_PREFIX ]; then
    error_exit "$LINENO" "incorrect use of script. TAG_PREFIX (e.g. master, staging) not defined!"
fi

log_info "logging in dockerhub..."
bash ci/helpers/dockerhub_login.bash

# the temporary multi-arch manifest that was built, pushed and fused earlier in the CI run
GIT_SHA="${GITHUB_SHA:-$(git rev-parse HEAD)}"
readonly GIT_SHA
from_docker_image_tag="${TAG_PREFIX}-tmp-${GIT_SHA}"
readonly from_docker_image_tag

# final destination tags: '<prefix>-latest' and a dated '<prefix>-DATE.GIT_SHA'
dated_tag="${TAG_PREFIX}-$(date --utc +"%Y-%m-%d--%H-%M").${GIT_SHA}"
dest_tags=("${TAG_PREFIX}-latest" "${dated_tag}")
readonly dest_tags

services="$(docker compose --file services/docker-compose-deploy.yml config --services)"
readonly services

for service in ${services}; do
    source_image="${DOCKER_REGISTRY}/${service}:${from_docker_image_tag}"
    tag_args=()
    for dest_tag in "${dest_tags[@]}"; do
        tag_args+=(--tag "${DOCKER_REGISTRY}/${service}:${dest_tag}")
    done
    log_info "promoting ${source_image} -> ${dest_tags[*]}"
    docker buildx imagetools create "${tag_args[@]}" "${source_image}"
done

log_info "complete!"

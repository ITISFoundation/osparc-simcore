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
if [ ! -v DIGESTS_FILE ] || [ ! -f "${DIGESTS_FILE}" ]; then
    error_exit "$LINENO" "incorrect use of script. DIGESTS_FILE (path to the merged service->arch->digest JSON, see ci/helpers/merge_digests.bash) not defined or missing!"
fi

log_info "logging in dockerhub..."
bash ci/helpers/dockerhub_login.bash

GIT_SHA="${GITHUB_SHA:-$(git rev-parse HEAD)}"
readonly GIT_SHA

# final destination tags: '<prefix>-latest' and a dated '<prefix>-DATE.GIT_SHA'
dated_tag="${TAG_PREFIX}-$(date --utc +"%Y-%m-%d--%H-%M").${GIT_SHA}"
dest_tags=("${TAG_PREFIX}-latest" "${dated_tag}")
readonly dest_tags

services="$(docker compose --file services/docker-compose-deploy.yml config --services)"
readonly services

# builds the final multi-arch manifest directly from the per-arch digests pushed
# earlier in the CI run (no intermediate tag is ever created in the registry)
for service in ${services}; do
    amd64_digest="$(jq -r --arg s "${service}" '.[$s].amd64 // empty' "${DIGESTS_FILE}")"
    arm64_digest="$(jq -r --arg s "${service}" '.[$s].arm64 // empty' "${DIGESTS_FILE}")"
    if [ -z "${amd64_digest}" ] || [ -z "${arm64_digest}" ]; then
        error_exit "$LINENO" "missing amd64/arm64 digest for service ${service} in ${DIGESTS_FILE}"
    fi

    tag_args=()
    for dest_tag in "${dest_tags[@]}"; do
        tag_args+=(--tag "${DOCKER_REGISTRY}/${service}:${dest_tag}")
    done

    log_info "promoting ${service}@{${amd64_digest},${arm64_digest}} -> ${dest_tags[*]}"
    docker buildx imagetools create "${tag_args[@]}" \
        "${DOCKER_REGISTRY}/${service}@${amd64_digest}" \
        "${DOCKER_REGISTRY}/${service}@${arm64_digest}"
done

log_info "complete!"

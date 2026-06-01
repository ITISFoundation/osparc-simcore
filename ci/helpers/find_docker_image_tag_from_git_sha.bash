#!/usr/bin/env bash
# Usage: find_docker_image_tag_from_git_sha.bash
#
# returns the full image tag corresponding to the git tag name that shall be used

# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

my_dir="$(dirname "$0")"
source "$my_dir/../../scripts/helpers/logger.bash"

log_info "Retrieving SHA for tag ${GIT_TAG}"
readonly GIT_COMMIT_SHA=$(git show-ref -s "${GIT_TAG}")
if [ -z "${GIT_COMMIT_SHA}" ]; then
    error_exit "$LINENO" "could not resolve SHA for git tag '${GIT_TAG}'"
fi
log_info "Found SHA for tag ${GIT_COMMIT_SHA}"

if [ ! -v ORG ] || [ ! -v REPO ] || [ ! -v TAG_PATTERN ]; then
    error_exit "$LINENO" "incorrect use of script. ORG/REPO/TAG_PATTERN and GIT_TAG must be defined"
fi

if [ -z "${ORG:-}" ] || [ -z "${REPO:-}" ] || [ -z "${TAG_PATTERN:-}" ]; then
    error_exit "$LINENO" "incorrect use of script. ORG/REPO/TAG_PATTERN and GIT_TAG must be non-empty"
fi

# Optional env vars with safe defaults
REGISTRY_HOST=${REGISTRY_HOST:-registry-1.docker.io}
PAGE_SIZE=${PAGE_SIZE:-100}
MAX_PAGES=${MAX_PAGES:-5}
CURL_RETRY=${CURL_RETRY:-3}
CURL_RETRY_DELAY=${CURL_RETRY_DELAY:-1}
CURL_CONNECT_TIMEOUT=${CURL_CONNECT_TIMEOUT:-10}
CURL_MAX_TIME=${CURL_MAX_TIME:-60}

image_name="${ORG}/${REPO}"
tags_url="https://${REGISTRY_HOST}/v2/${image_name}/tags/list?n=${PAGE_SIZE}"

tmp_headers=$(mktemp)
trap 'rm -f "$tmp_headers"' EXIT

curl_base_args=(
    --silent
    --show-error
    --location
    --retry "$CURL_RETRY"
    --retry-delay "$CURL_RETRY_DELAY"
    --retry-all-errors
    --connect-timeout "$CURL_CONNECT_TIMEOUT"
    --max-time "$CURL_MAX_TIME"
)

request_headers() {
    local url="$1"
    local auth_header="${2:-}"
    if [ -n "$auth_header" ]; then
        curl "${curl_base_args[@]}" -D "$tmp_headers" -o /dev/null -H "$auth_header" "$url" || true
    else
        # We expect 401 on first unauthenticated call for most registries
        curl "${curl_base_args[@]}" -D "$tmp_headers" -o /dev/null "$url" || true
    fi
}

extract_www_authenticate() {
    awk 'BEGIN{IGNORECASE=1} /^Www-Authenticate:/ {sub(/^[^:]*: /, ""); print; exit}' "$tmp_headers" | tr -d '\r'
}

extract_param() {
    local header="$1"
    local key="$2"
    echo "$header" | sed -nE "s/.*${key}=\"([^\"]+)\".*/\1/p"
}

build_token_url() {
    local realm="$1"
    local service="$2"
    local scope="$3"

    local sep='?'
    local url="$realm"

    if [ -n "$service" ]; then
        url="${url}${sep}service=${service}"
        sep='&'
    fi

    if [ -n "$scope" ]; then
        url="${url}${sep}scope=${scope}"
    fi

    echo "$url"
}

log_info "Listing tags for ${image_name} from registry host ${REGISTRY_HOST}"
request_headers "$tags_url"
www_auth=$(extract_www_authenticate)

auth_header=""
if [ -n "$www_auth" ]; then
    scheme=$(echo "$www_auth" | awk '{print $1}')
    if [ "$scheme" != "Bearer" ]; then
        error_exit "$LINENO" "unsupported auth scheme in challenge: ${www_auth}"
    fi

    realm=$(extract_param "$www_auth" realm)
    service=$(extract_param "$www_auth" service)
    scope=$(extract_param "$www_auth" scope)

    if [ -z "$scope" ]; then
        scope="repository:${image_name}:pull"
    fi
    if [ -z "$realm" ]; then
        error_exit "$LINENO" "could not parse token realm from challenge: ${www_auth}"
    fi

    token_url=$(build_token_url "$realm" "$service" "$scope")
    registry_username="${REGISTRY_USERNAME:-${DOCKER_USERNAME:-}}"
    registry_password="${REGISTRY_PASSWORD:-${DOCKER_PASSWORD:-}}"

    log_info "Retrieving bearer token ..."
    if [ -n "$registry_username" ] || [ -n "$registry_password" ]; then
        token_json=$(curl "${curl_base_args[@]}" --fail -u "${registry_username}:${registry_password}" "$token_url")
    else
        token_json=$(curl "${curl_base_args[@]}" --fail "$token_url")
    fi

    token=$(echo "$token_json" | jq -r '.token // .access_token // empty')
    if [ -z "$token" ]; then
        error_exit "$LINENO" "token endpoint did not return token/access_token"
    fi
    auth_header="Authorization: Bearer ${token}"
fi

all_tags=()
page=1
next_url="$tags_url"

while [ -n "$next_url" ] && [ "$page" -le "$MAX_PAGES" ]; do
    if [ -n "$auth_header" ]; then
        response=$(curl "${curl_base_args[@]}" --fail -H "$auth_header" "$next_url")
    else
        response=$(curl "${curl_base_args[@]}" --fail "$next_url")
    fi

    while IFS= read -r tag; do
        [ -n "$tag" ] && all_tags+=("$tag")
    done < <(echo "$response" | jq -r '.tags[]?')

    request_headers "$next_url" "$auth_header"
    link_header=$(awk 'BEGIN{IGNORECASE=1} /^Link:/ {sub(/^[^:]*: /, ""); print; exit}' "$tmp_headers" | tr -d '\r')

    if [ -n "$link_header" ] && echo "$link_header" | grep -q 'rel="next"'; then
        raw_next=$(echo "$link_header" | sed -nE 's/^<([^>]+)>.*/\1/p')
        if [[ "$raw_next" == http* ]]; then
            next_url="$raw_next"
        else
            next_url="https://${REGISTRY_HOST}${raw_next}"
        fi
    else
        next_url=""
    fi

    page=$((page + 1))
done

if [ "$page" -gt "$MAX_PAGES" ] && [ -n "$next_url" ]; then
    log_warning "Reached MAX_PAGES=${MAX_PAGES}. Results may be incomplete."
fi

for j in "${all_tags[@]}"; do
    if [[ ${j} =~ ${TAG_PATTERN} ]] && [[ ${j} =~ ${GIT_COMMIT_SHA} ]]; then
        echo "${j}"
        exit 0
    fi
done

error_exit "$LINENO" "could not find image:${GIT_TAG} with ${GIT_COMMIT_SHA}. Is the image available in the registry?"

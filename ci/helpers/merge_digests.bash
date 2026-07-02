#!/usr/bin/env bash
# Usage: merge_digests.bash <amd64-digests-dir> <arm64-digests-dir> <output-file>
#
# Merges the buildx bake --metadata-file JSON files (one per component: backend/frontend)
# found in each per-architecture directory into a single JSON map:
#   {"<service>": {"amd64": "sha256:...", "arm64": "sha256:..."}, ...}

# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

my_dir="$(dirname "$0")"
# shellcheck source=/dev/null
source "$my_dir/../../scripts/helpers/logger.bash"

if [ "$#" -ne 3 ]; then
    error_exit "$LINENO" "Usage: $0 <amd64-digests-dir> <arm64-digests-dir> <output-file>"
fi

readonly amd64_dir="$1"
readonly arm64_dir="$2"
readonly output_file="$3"

merge_metadata_files() {
    local dir="$1"
    # shellcheck disable=SC2206
    local files=($dir/digests-*.json)
    jq -s 'reduce .[] as $item ({}; . * $item)' "${files[@]}"
}

amd64_json="$(merge_metadata_files "${amd64_dir}")"
readonly amd64_json
arm64_json="$(merge_metadata_files "${arm64_dir}")"
readonly arm64_json

jq -n \
    --argjson amd64 "${amd64_json}" \
    --argjson arm64 "${arm64_json}" \
    '($amd64 | keys) as $services
     | reduce $services[] as $s
         ({}; . + {($s): {amd64: $amd64[$s]."containerimage.digest", arm64: $arm64[$s]."containerimage.digest"}})' \
    > "${output_file}"

log_info "merged digests written to ${output_file}:"
cat "${output_file}"

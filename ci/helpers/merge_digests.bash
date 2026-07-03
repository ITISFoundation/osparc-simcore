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

tmp_dir="$(mktemp -d)"
readonly tmp_dir
trap 'rm -rf "${tmp_dir}"' EXIT

merge_metadata_files() {
    local dir="$1"
    local out="$2"

    shopt -s nullglob  # Unmatched globs expand to empty, not literal
    local files=("${dir}"/digests-*.json)
    shopt -u nullglob

    if [ "${#files[@]}" -eq 0 ]; then
        error_exit "$LINENO" "no digest metadata files found in ${dir} (expected digests-*.json)"
    fi

    jq -s 'reduce .[] as $item ({}; . * $item)' "${files[@]}" > "${out}"
}

merge_metadata_files "${amd64_dir}" "${tmp_dir}/amd64.json"
merge_metadata_files "${arm64_dir}" "${tmp_dir}/arm64.json"

# use --slurpfile (reads file contents internally) instead of --argjson (passes content
# via argv) since the merged bake metadata can be large enough to exceed ARG_MAX
jq -n \
    --slurpfile amd64 "${tmp_dir}/amd64.json" \
    --slurpfile arm64 "${tmp_dir}/arm64.json" \
    '($amd64[0] | keys) as $services
     | reduce $services[] as $s
         ({}; . + {($s): {amd64: $amd64[0][$s]."containerimage.digest", arm64: $arm64[0][$s]."containerimage.digest"}})' \
    > "${output_file}"

log_info "merged digests written to ${output_file}:"
cat "${output_file}"

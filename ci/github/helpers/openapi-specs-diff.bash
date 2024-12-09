#!/bin/bash

# Recursively checks if all openapi specs within a local osparc-simcore revision are different/backwards compatible with a remote base
# Example:
#    bash osparc-simcore/ci/github/helpers/openapi-specs-diff.bash diff \
#      https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/refs/heads/master \
#      ./osparc-simcore/
# or
#    bash osparc-simcore/ci/github/helpers/openapi-specs-diff.bash breaking \
#      https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/refs/heads/master \
#      ./osparc-simcore/
#
# The script generates github error annotations for better being able to locate issues.

operation=$1
base_remote=$2
revision_local=$3

repo_base_dir=$(realpath "$(dirname "${BASH_SOURCE[0]}")/../../..")
openapi_specs=$(find "${revision_local}" -type f \( -name 'openapi.json' -o -name 'openapi.yaml' \) -not -path '*/.*' -exec realpath --relative-to="${revision_local}" {} \;)

cd "${revision_local}" || exit 1 # required to mount correct dir for diff tool


function run_diff_tool() {
  exit_status=0
  for spec in ${openapi_specs}; do
    echo "Comparing ${spec}"
    if ! "${repo_base_dir}/scripts/openapi-diff.bash" "$@" "${base_remote}/${spec}" "/specs/${spec}"; then
      echo "::error file=${spec}:: Error when checking ${spec}"
      exit_status=$(("${exit_status}" + "1"))
    fi
    printf "%0.s=" {1..100} && printf "\n"
  done

  exit "${exit_status}"
}


if [[ "${operation}" == "diff" ]]; then
  run_diff_tool "diff" "--fail-on-diff"
elif [[ "${operation}" == "breaking" ]]; then
  run_diff_tool "breaking" "--fail-on" "ERR"
else
  echo "the operation '${operation}' is not supported"
  exit 1
fi

#!/bin/bash

# Recursively checks if all openapi specs within a local osparc-simcore clone are backwards compatible with a remote clone
# Example: bash osparc-simcore/ci/github/helpers/openapi-specs-backwards-compatibility.bash \
#    https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/refs/heads/master
#    ./osparc-simcore/

base_remote=$1
revision_local=$2

repo_base_dir=$(realpath "$(dirname "${BASH_SOURCE[0]}")/../../..")
openapi_specs=$(find "${revision_local}" -type f \( -name 'openapi.json' -o -name 'openapi.yaml' \) -not -path '*/.*' -exec realpath --relative-to="${revision_local}" {} \;)

cd "${revision_local}" || exit 1 # required to mount correct dir for diff tool

exit_status=0
for spec in ${openapi_specs}; do
  echo "Comparing ${spec}"
  "${repo_base_dir}/scripts/openapi-diff.bash" breaking --fail-on ERR "${base_remote}/${spec}" "/specs/${spec}"
  exit_status=$(("${exit_status}" + $?))
  printf "%0.s=" {1..100} && printf "\n"
done

exit "${exit_status}"

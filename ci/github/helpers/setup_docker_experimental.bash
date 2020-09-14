#!/bin/bash
# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

mkdir --parents ~/.docker/
echo '{"experimental":"enabled"}' > ~/.docker/config.json

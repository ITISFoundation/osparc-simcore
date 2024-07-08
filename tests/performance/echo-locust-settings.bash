#!/bin/bash

set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes

python locust_settings.py "$@" | jq -r 'to_entries | .[] | "\(.key)=\(.value)"'

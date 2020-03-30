#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

mkdir --parents ~/.docker/
echo '{"experimental":"enabled"}' > ~/.docker/config.json
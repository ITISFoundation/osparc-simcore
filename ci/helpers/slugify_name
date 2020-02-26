#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

slugify () {
    echo "$1" | iconv -t ascii//TRANSLIT | sed -r s/[~$'\^']+//g | sed -r s/[^a-zA-Z0-9]+/-/g | sed -r s/^-+\|-+$//g | tr A-Z a-z
}

echo "$(slugify $1)"

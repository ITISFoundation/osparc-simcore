#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

sc-pg discover \
        --user "${POSTGRES_USER}" \
        --password "${POSTGRES_PASSWORD}" \
        --host "${POSTGRES_HOST}" \
        --port "${POSTGRES_PORT}" \
        --database "${POSTGRES_DB}"

exec "$@"

#!/bin/bash
#
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

printenv
echo "Running application ..."
echo "  User    :`id $(whoami)`"
echo "  Workdir :`pwd`"

start-notebook.sh --NotebookApp.password=$(python -c "from notebook.auth import passwd; print(passwd('${MAINTENANCE_PASSWORD}'))")

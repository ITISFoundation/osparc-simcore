#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

uname -a
lsb_release -a

if command -v python; then
    python --version
fi

if command -v docker; then
    docker -v
fi

if command -v docker-compose; then
    docker-compose version
fi

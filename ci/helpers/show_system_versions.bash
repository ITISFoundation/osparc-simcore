#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

echo "------------------------------ environs -----------------------------------"
env

echo "------------------------------ uname -----------------------------------"
uname -a
lsb_release -a

echo "------------------------------ python -----------------------------------"
if command -v python; then
    python --version
fi

echo "------------------------------ python3 -----------------------------------"
if command -v python3; then
    python3 --version
fi

echo "------------------------------ docker -----------------------------------"
if command -v docker; then
    docker version
fi

echo "------------------------------ docker-compose -----------------------------------"
if command -v docker-compose; then
    docker-compose version
fi

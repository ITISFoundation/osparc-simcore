#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

echo "------------------------------ environs -----------------------------------"
env | sort

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

echo "------------------------------ pip -----------------------------------"
if command -v pip; then
  pip --version
  echo "cache location:"
  pip cache dir
fi

echo "------------------------------ uv -----------------------------------"
if command -v uv; then
  uv --version
  echo "cache location:"
  uv cache dir
fi

echo "------------------------------ docker -----------------------------------"
if command -v docker; then
  docker version
fi

echo "------------------------------ docker buildx-----------------------------------"
if command -v docker; then
  docker buildx version
fi

echo "------------------------------ docker-compose -----------------------------------"
if command -v docker-compose; then
  docker-compose version
fi

echo "------------------------------ docker compose -----------------------------------"
if command -v docker; then
  docker compose version
fi

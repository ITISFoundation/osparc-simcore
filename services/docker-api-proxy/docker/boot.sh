#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "$INFO" "User :$(id "$(whoami)")"

#
# RUNNING application
#
socat TCP-LISTEN:8889,fork,reuseaddr UNIX-CONNECT:/var/run/docker.sock &

DOCKER_API_PROXY_ENCRYPTED_PASSWORD=$(caddy hash-password --plaintext "$DOCKER_API_PROXY_PASSWORD") \
  caddy run --adapter caddyfile --config /etc/caddy/Caddyfile

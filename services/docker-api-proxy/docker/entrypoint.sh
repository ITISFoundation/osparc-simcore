#!/bin/sh
#
# - Executes *inside* of the container upon start as --user [default root]
# - Notice that the container *starts* as --user [default root] but
#   *runs* as non-root user [scu]
#
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

echo "$INFO" "Entrypoint for stage ${SC_BUILD_TARGET} ..."
echo "$INFO" "User :$(id "$(whoami)")"

#chown -R ${SC_USER_NAME}:${SC_USER_NAME} /var/run/docker.sock


# Appends docker group if socket is mounted
DOCKER_MOUNT=/var/run/docker.sock
if stat $DOCKER_MOUNT >/dev/null 2>&1; then
  echo "INFO: detected docker socket is mounted, adding user to group..."
  GROUPID=$(stat -c %g $DOCKER_MOUNT) # Alpine uses `-c` instead of `--format`
  GROUPNAME=scdocker

  # Check if a group with the specified GID exists
  if ! addgroup -g "$GROUPID" $GROUPNAME >/dev/null 2>&1; then
    echo "WARNING: docker group with GID $GROUPID already exists, getting group name..."
    # Get the group name based on GID
    GROUPNAME=$(getent group | awk -F: "\$3 == $GROUPID {print \$1}")
    echo "WARNING: docker group with GID $GROUPID has name $GROUPNAME"
  fi

  # Add the user to the group
  adduser "$SC_USER_NAME" $GROUPNAME
fi


exec gosu "$SC_USER_NAME" "$@"

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
WARNING="WARNING: [$(basename "$0")] "
ERROR="ERROR: [$(basename "$0")] "

# Read self-signed SSH certificates (if applicable)
#
# In case efs-guardian must access a docker registry in a secure way using
# non-standard certificates (e.g. such as self-signed certificates), this call is needed.
# It needs to be executed as root. Also required to any access for example to secure rabbitmq.
update-ca-certificates

echo "$INFO" "Entrypoint for stage ${SC_BUILD_TARGET} ..."
echo "$INFO" "User :$(id "$(whoami)")"
echo "$INFO" "Workdir : $(pwd)"
echo "$INFO" "User : $(id scu)"
echo "$INFO" "python : $(command -v python)"
echo "$INFO" "pip : $(command -v pip)"

#
# DEVELOPMENT MODE
# - expects docker run ... -v $(pwd):$SC_DEVEL_MOUNT
# - mounts source folders
# - deduces host's uid/gip and assigns to user within docker
#
if [ "${SC_BUILD_TARGET}" = "development" ]; then
  echo "$INFO" "development mode detected..."
  stat "${SC_DEVEL_MOUNT}" >/dev/null 2>&1 ||
    (echo "$ERROR" "You must mount '$SC_DEVEL_MOUNT' to deduce user and group ids" && exit 1)

  echo "$INFO" "setting correct user id/group id..."
  HOST_USERID=$(stat --format=%u "${SC_DEVEL_MOUNT}")
  HOST_GROUPID=$(stat --format=%g "${SC_DEVEL_MOUNT}")
  CONT_GROUPNAME=$(getent group "${HOST_GROUPID}" | cut --delimiter=: --fields=1)
  if [ "$HOST_USERID" -eq 0 ]; then
    echo "$WARNING" "Folder mounted owned by root user... adding $EFS_USER_NAME to root..."
    adduser "$EFS_USER_NAME" root
  else
    echo "$INFO" "Folder mounted owned by user $HOST_USERID:$HOST_GROUPID-'$CONT_GROUPNAME'..."
    # take host's credentials in $EFS_USER_NAME
    if [ -z "$CONT_GROUPNAME" ]; then
      echo "$WARNING" "Creating new group grp$EFS_USER_NAME"
      CONT_GROUPNAME=grp$EFS_USER_NAME
      addgroup --gid "$HOST_GROUPID" "$CONT_GROUPNAME"
    else
      echo "$INFO" "group already exists"
    fi
    echo "$INFO" "Adding $EFS_USER_NAME to group $CONT_GROUPNAME..."
    adduser "$EFS_USER_NAME" "$CONT_GROUPNAME"

    echo "$WARNING" "Changing ownership [this could take some time]"
    echo "$INFO" "Changing $EFS_USER_NAME:$EFS_USER_NAME ($EFS_USER_ID:$EFS_USER_ID) to $EFS_USER_NAME:$CONT_GROUPNAME ($HOST_USERID:$HOST_GROUPID)"
    usermod --uid "$HOST_USERID" --gid "$HOST_GROUPID" "$EFS_USER_NAME"

    echo "$INFO" "Changing group properties of files around from $EFS_USER_ID to group $CONT_GROUPNAME"
    fdfind --owner ":$EFS_USER_ID" --exclude proc --exec-batch chgrp --no-dereference "$CONT_GROUPNAME"
    echo "$INFO" "Changing ownership properties of files around from $EFS_USER_ID to group $CONT_GROUPNAME"
    fdfind --owner "$EFS_USER_ID:" --exclude proc --exec-batch chown --no-dereference "$EFS_USER_NAME"
  fi
fi

# Appends docker group if socket is mounted
DOCKER_MOUNT=/var/run/docker.sock
if stat $DOCKER_MOUNT >/dev/null 2>&1; then
  echo "$INFO detected docker socket is mounted, adding user to group..."
  GROUPID=$(stat --format=%g $DOCKER_MOUNT)
  GROUPNAME=scdocker

  if ! addgroup --gid "$GROUPID" $GROUPNAME >/dev/null 2>&1; then
    echo "$WARNING docker group with $GROUPID already exists, getting group name..."
    # if group already exists in container, then reuse name
    GROUPNAME=$(getent group "${GROUPID}" | cut --delimiter=: --fields=1)
    echo "$WARNING docker group with $GROUPID has name $GROUPNAME"
  fi
  adduser "$EFS_USER_NAME" "$GROUPNAME"
fi

echo "$INFO Starting $* ..."
echo "  $(whoami) rights    : $(id $whoami))"
echo "  local dir : $(ls -al)"

exec "$@"

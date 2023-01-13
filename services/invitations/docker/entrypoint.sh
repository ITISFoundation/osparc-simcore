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
    echo "$WARNING" "Folder mounted owned by root user... adding $SC_USER_NAME to root..."
    adduser "$SC_USER_NAME" root
  else
    echo "$INFO" "Folder mounted owned by user $HOST_USERID:$HOST_GROUPID-'$CONT_GROUPNAME'..."
    # take host's credentials in $SC_USER_NAME
    if [ -z "$CONT_GROUPNAME" ]; then
      echo "$WARNING" "Creating new group grp$SC_USER_NAME"
      CONT_GROUPNAME=grp$SC_USER_NAME
      addgroup --gid "$HOST_GROUPID" "$CONT_GROUPNAME"
    else
      echo "$INFO" "group already exists"
    fi
    echo "$INFO" "Adding $SC_USER_NAME to group $CONT_GROUPNAME..."
    adduser "$SC_USER_NAME" "$CONT_GROUPNAME"

    echo "$WARNING" "Changing ownership [this could take some time]"
    echo "$INFO" "Changing $SC_USER_NAME:$SC_USER_NAME ($SC_USER_ID:$SC_USER_ID) to $SC_USER_NAME:$CONT_GROUPNAME ($HOST_USERID:$HOST_GROUPID)"
    usermod --uid "$HOST_USERID" --gid "$HOST_GROUPID" "$SC_USER_NAME"

    echo "$INFO" "Changing group properties of files around from $SC_USER_ID to group $CONT_GROUPNAME"
    find / -path /proc -prune -o -group "$SC_USER_ID" -exec chgrp --no-dereference "$CONT_GROUPNAME" {} \;
    # change user property of files already around
    echo "$INFO" "Changing ownership properties of files around from $SC_USER_ID to group $CONT_GROUPNAME"
    find / -path /proc -prune -o -user "$SC_USER_ID" -exec chown --no-dereference "$SC_USER_NAME" {} \;
  fi
fi

if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then
  # NOTE: production does NOT pre-installs ptvsd
  pip install --no-cache-dir ptvsd
fi

echo "$INFO Starting $* ..."
echo "  $SC_USER_NAME rights    : $(id "$SC_USER_NAME")"
echo "  local dir : $(ls -al)"

exec gosu "$SC_USER_NAME" "$@"

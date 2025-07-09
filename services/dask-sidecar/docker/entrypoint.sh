#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "
WARNING="WARNING: [$(basename "$0")] "
ERROR="ERROR: [$(basename "$0")] "

# Read self-signed SSH certificates (if applicable)
#
# In case storage must access a docker registry in a secure way using
# non-standard certificates (e.g. such as self-signed certificates), this call is needed.
# It needs to be executed as root.
update-ca-certificates

# This entrypoint script:
#
# - Executes *inside* of the container upon start as --user [default root]
# - Notice that the container *starts* as --user [default root] but
#   *runs* as non-root user [scu]
#
echo "$INFO" "Entrypoint for stage ${SC_BUILD_TARGET} ..."
echo User :"$(id "$(whoami)")"
echo Workdir :"$(pwd)"
echo scuUser :"$(id scu)"

if [ "${SC_BUILD_TARGET}" = "development" ]; then
  echo "$INFO" "development mode detected..."
  # NOTE: expects docker run ... -v $(pwd):/devel/services/dask-sidecar
  DEVEL_MOUNT="/devel/services/dask-sidecar"

  stat $DEVEL_MOUNT >/dev/null 2>&1 ||
    (echo "$ERROR" "You must mount '$DEVEL_MOUNT' to deduce user and group ids" && exit 1)

  echo "setting correct user id/group id..."
  HOST_USERID=$(stat --format=%u "${DEVEL_MOUNT}")
  HOST_GROUPID=$(stat --format=%g "${DEVEL_MOUNT}")
  CONT_GROUPNAME=$(getent group "${HOST_GROUPID}" | cut --delimiter=: --fields=1)
  if [ "$HOST_USERID" -eq 0 ]; then
    echo "Warning: Folder mounted owned by root user... adding $SC_USER_NAME to root..."
    adduser "$SC_USER_NAME" root
  else
    echo "Folder mounted owned by user $HOST_USERID:$HOST_GROUPID-'$CONT_GROUPNAME'..."
    # take host's credentials in $SC_USER_NAME
    if [ -z "$CONT_GROUPNAME" ]; then
      echo "Creating new group my$SC_USER_NAME"
      CONT_GROUPNAME=my$SC_USER_NAME
      addgroup --gid "$HOST_GROUPID" "$CONT_GROUPNAME"
    else
      echo "group already exists"
    fi
    echo "adding $SC_USER_NAME to group $CONT_GROUPNAME..."
    adduser "$SC_USER_NAME" "$CONT_GROUPNAME"

    echo "changing $SC_USER_NAME:$SC_USER_NAME ($SC_USER_ID:$SC_USER_ID) to $SC_USER_NAME:$CONT_GROUPNAME ($HOST_USERID:$HOST_GROUPID)"
    usermod --uid "$HOST_USERID" --gid "$HOST_GROUPID" "$SC_USER_NAME"

    echo "Changing group properties of files around from $SC_USER_ID to group $CONT_GROUPNAME"
    fdfind --owner ":$SC_USER_ID" --exclude proc --exec-batch chgrp --no-dereference "$CONT_GROUPNAME"
    echo "Changing ownership properties of files around from $SC_USER_ID to group $CONT_GROUPNAME"
    fdfind --owner "$SC_USER_ID:" --exclude proc --exec-batch chown --no-dereference "$SC_USER_NAME"
  fi
fi

if [ ${DASK_START_AS_SCHEDULER+x} ]; then

  echo "$INFO Starting $* as SCHEDULER ..."
  echo "  $SC_USER_NAME rights    : $(id "$SC_USER_NAME")"
  echo "  local dir : $(ls -al)"

else

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
    adduser "$SC_USER_NAME" "$GROUPNAME"
  fi

  echo "$INFO ensuring write rights on computational shared folder ..."
  mkdir --parents "${SIDECAR_COMP_SERVICES_SHARED_FOLDER}"
  chown --recursive "$SC_USER_NAME":"$GROUPNAME" "${SIDECAR_COMP_SERVICES_SHARED_FOLDER}"

  echo "$INFO Starting $* as WORKER ..."
  echo "  $SC_USER_NAME rights    : $(id "$SC_USER_NAME")"
  echo "  local dir : $(ls -al)"
  echo "  computational shared data dir : $(ls -al "${SIDECAR_COMP_SERVICES_SHARED_FOLDER}")"
fi

exec gosu "$SC_USER_NAME" "$@"

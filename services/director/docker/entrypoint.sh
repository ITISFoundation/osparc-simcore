#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "
WARNING="WARNING: [$(basename "$0")] "
ERROR="ERROR: [$(basename "$0")] "

# Read self-signed SSH certificates (if applicable)
#
# In case the director must access a docker registry in a secure way using
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
echo "$INFO" "User    :$(id "$(whoami)")"
echo "$INFO" "Workdir :$(pwd)"
echo  scuUser :"$(id scu)"

if [ "${SC_BUILD_TARGET}" = "development" ]
then
    # NOTE: expects docker run ... -v $(pwd):/devel/services/director
    DEVEL_MOUNT=/devel/services/director

    stat $DEVEL_MOUNT > /dev/null 2>&1 || \
        (echo "$ERROR" "You must mount '$DEVEL_MOUNT' to deduce user and group ids" && exit 1) # FIXME: exit does not stop script

    echo "setting correct user id/group id..."
    HOST_USERID=$(stat --format=%u "${DEVEL_MOUNT}")
    HOST_GROUPID=$(stat --format=%g "${DEVEL_MOUNT}")
    CONT_GROUPNAME=$(getent group "${HOST_GROUPID}" | cut --delimiter=: --fields=1)
    if [ "$HOST_USERID" -eq 0 ]
    then
        echo "Warning: Folder mounted owned by root user... adding $SC_USER_NAME to root..."
        adduser "$SC_USER_NAME" root
    else
        echo "Folder mounted owned by user $HOST_USERID:$HOST_GROUPID-'$CONT_GROUPNAME'..."
        # take host's credentials in $SC_USER_NAME
        if [ -z "$CONT_GROUPNAME" ]
        then
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
        find / -path /proc -prune -o -group "$SC_USER_ID" -exec chgrp --no-dereference "$CONT_GROUPNAME" {} \;
        # change user property of files already around
        echo "Changing ownership properties of files around from $SC_USER_ID to group $CONT_GROUPNAME"
        find / -path /proc -prune -o -user "$SC_USER_ID" -exec chown --no-dereference "$SC_USER_NAME" {} \;
    fi
fi


if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]
then
  # NOTE: production does NOT pre-installs ptvsd
  python3 -m pip install ptvsd
fi

# Appends docker group if socket is mounted
DOCKER_MOUNT=/var/run/docker.sock
if stat $DOCKER_MOUNT > /dev/null 2>&1
then
    echo "$INFO detected docker socket is mounted, adding user to group..."
    GROUPID=$(stat --format=%g $DOCKER_MOUNT)
    GROUPNAME=scdocker

    if ! addgroup --gid "$GROUPID" $GROUPNAME > /dev/null 2>&1
    then
        echo "$WARNING docker group with $GROUPID already exists, getting group name..."
        # if group already exists in container, then reuse name
        GROUPNAME=$(getent group "${GROUPID}" | cut --delimiter=: --fields=1)
        echo "$WARNING docker group with $GROUPID has name $GROUPNAME"
    fi
    adduser "$SC_USER_NAME" "$GROUPNAME"
fi

echo "$INFO Starting $* ..."
echo "  $SC_USER_NAME rights    : $(id "$SC_USER_NAME")"
echo "  local dir : $(ls -al)"

exec gosu "$SC_USER_NAME" "$@"

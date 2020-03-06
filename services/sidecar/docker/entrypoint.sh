#!/bin/sh
#
INFO="INFO: [$(basename "$0")] "
ERROR="ERROR: [$(basename "$0")] "

# This entrypoint script:
#
# - Executes *inside* of the container upon start as --user [default root]
# - Notice that the container *starts* as --user [default root] but
#   *runs* as non-root user [scu]
#
echo "$INFO" "Entrypoint for stage ${SC_BUILD_TARGET} ..."
echo "  User    :$(id "$(whoami)")"
echo "  Workdir :$(pwd)"
echo "  scuUser :$(id scu)"


USERNAME=scu
GROUPNAME=scu

if [ "${SC_BUILD_TARGET}" = "development" ]
then
    echo "$INFO" "development mode detected..."
    # NOTE: expects docker run ... -v $(pwd):/devel/services/sidecar
    DEVEL_MOUNT=/devel/services/sidecar

    stat $DEVEL_MOUNT > /dev/null 2>&1 || \
        (echo "$ERROR" "You must mount '$DEVEL_MOUNT' to deduce user and group ids" && exit 1) # FIXME: exit does not stop script

    USERID=$(stat -c %u $DEVEL_MOUNT)
    GROUPID=$(stat -c %g $DEVEL_MOUNT)
    GROUPNAME=$(getent group "${GROUPID}" | cut -d: -f1)

    if [ "$USERID" -eq 0 ]
    then
        echo "$INFO" "mounted folder from root, adding scu to root..."
        addgroup scu root
    else
        # take host's credentials in scu
        if [ -z "$GROUPNAME" ]
        then
            echo "$INFO" "mounted folder from $USERID, creating new group..."
            GROUPNAME=host_group
            addgroup -g "$GROUPID" $GROUPNAME
        else
            echo "$INFO" "mounted folder from $USERID, adding scu to $GROUPNAME..."
            addgroup scu $GROUPNAME
        fi

        deluser scu > /dev/null 2>&1
        adduser -u "$USERID" -G $GROUPNAME -D -s /bin/sh scu
    fi
fi



# Appends docker group if socket is mounted
DOCKER_MOUNT=/var/run/docker.sock


if stat $DOCKER_MOUNT > /dev/null 2>&1
then
    GROUPID=$(stat -c %g $DOCKER_MOUNT)
    GROUPNAME=scdocker


    if ! addgroup -g "$GROUPID" $GROUPNAME > /dev/null 2>&1
    then
        # if group already exists in container, then reuse name
        GROUPNAME=$(getent group "${GROUPID}" | cut -d: -f1)
    fi
    addgroup scu "$GROUPNAME"
fi

echo "$INFO" "Starting boot ..."
chown -R $USERNAME:"$GROUPNAME" /home/scu/input
chown -R $USERNAME:"$GROUPNAME" /home/scu/output
chown -R $USERNAME:"$GROUPNAME" /home/scu/log

exec su-exec scu "$@"

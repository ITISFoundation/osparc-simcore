#!/bin/sh

# This entrypoint script:
#
# - Executes *inside* of the container upon start as --user [default root]
# - Notice that the container *starts* as --user [default root] but
#   *runs* as non-root user [scu]
#
echo "Entrypoint for stage ${SC_BUILD_TARGET} ..."
echo "  User    :`id $(whoami)`"
echo "  Workdir :`pwd`"


if [[ ${SC_BUILD_TARGET} == "development" ]]
then

    # NOTE: expects docker run ... -v $(pwd):/devel/services/sidecar
    DEVEL_MOUNT=/devel/services/sidecar

    stat $DEVEL_MOUNT &> /dev/null || \
        (echo "ERROR: You must mount '$DEVEL_MOUNT' to deduce user and group ids" && exit 1) # FIXME: exit does not stop script

    USERID=$(stat -c %u $DEVEL_MOUNT)
    GROUPID=$(stat -c %g $DEVEL_MOUNT)
    GROUPNAME=$(getent group ${GROUPID} | cut -d: -f1)

    if [[ $USERID -eq 0 ]]
    then
        addgroup scu root
    else
        # take host's credentials in myu
        if [[ -z "$GROUPNAME" ]]
        then
            GROUPNAME=myu
            addgroup -g $GROUPID $GROUPNAME
        else
            addgroup scu $GROUPNAME
        fi

        deluser scu &> /dev/null
        adduser -u $USERID -G $GROUPNAME -D -s /bin/sh scu
    fi
fi



# Appends docker group if socket is mounted
DOCKER_MOUNT=/var/run/docker.sock

stat $DOCKER_MOUNT &> /dev/null
if [[ $? -eq 0 ]]
then
    GROUPID=$(stat -c %g $DOCKER_MOUNT)
    GROUPNAME=docker

    addgroup -g $GROUPID $GROUPNAME &> /dev/null
    if [[ $? -gt 0 ]]
    then
        # if group already exists in container, then reuse name
        GROUPNAME=$(getent group ${GROUPID} | cut -d: -f1)
    fi
    addgroup scu $GROUPNAME
fi



# Appends docker group if socket is mounted
DOCKER_MOUNT=/var/run/docker.sock

stat $DOCKER_MOUNT &> /dev/null
if [[ $? -eq 0 ]]
then
    GROUPID=$(stat -c %g $DOCKER_MOUNT)
    GROUPNAME=docker

    addgroup -g $GROUPID $GROUPNAME &> /dev/null
    if [[ $? -gt 0 ]]
    then
        # if group already exists in container, then reuse name
        GROUPNAME=$(getent group ${GROUPID} | cut -d: -f1)
    fi
    addgroup scu $GROUPNAME
fi

echo "Starting boot ..."
chown -R scu:scu /home/scu/input
chown -R scu:scu /home/scu/output
chown -R scu:scu /home/scu/log

su-exec scu "$@"

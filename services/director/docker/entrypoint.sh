#!/bin/sh

# This entrypoint script:
#
# - Executes *inside* of the container upon start as --user [default root]
# - Notice that the container *starts* as --user [default root] but
#   *runs* as non-root user [scu]
#
echo "Entrypoint for stage ${MY_BUILD_TARGET} ..."

if [[ ${MY_BUILD_TARGET} == "development" ]]
then
    echo "  User    :`id $(whoami)`"
    echo "  Workdir :`pwd`"

    # NOTE: expects docker run ... -v $(pwd):/devel/services/director
    DEVEL_MOUNT=/devel/services/director

    stat $DEVEL_MOUNT &> /dev/null || \
        (echo "ERROR: You must mount '$DEVEL_MOUNT' to deduce user and group ids" && exit 1) # FIXME: exit does not stop script

    USERID=$(stat -c %u $DEVEL_MOUNT)
    GROUPID=$(stat -c %g $DEVEL_MOUNT)

    deluser scu &> /dev/null
    addgroup -g $GROUPID scu
    adduser -u $USERID -G scu -D -s /bin/sh scu
fi



# Appends docker group if socket is mounted
DOCKER_MOUNT=/var/run/docker.sock

stat $DOCKER_MOUNT &> /dev/null
if [[ $? -eq 0 ]]
then
    GROUPID=$(stat -c %g $DOCKER_MOUNT)
    GROUPNAME=docker

    addgroup -g $GROUPID $GROUPNAME
    if [[ $? -gt 0 ]]
    then
        # if group already exists in container, then reuse name
        GROUPNAME=$(getent group ${GROUPID} | cut -d: -f1)
    fi
    addgroup scu $GROUPNAME
fi

echo "Starting boot ..."
su-exec scu "$@"

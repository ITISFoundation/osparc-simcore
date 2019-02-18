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

    # NOTE: expects docker run ... -v $(pwd):/devel/services/storage
    DEVEL_MOUNT=/devel/services/storage

    stat $DEVEL_MOUNT &> /dev/null || \
        (echo "ERROR: You must mount '$DEVEL_MOUNT' to deduce user and group ids" && exit 1) # FIXME: exit does not stop script

    USERID=$(stat -c %u $DEVEL_MOUNT)
    GROUPID=$(stat -c %g $DEVEL_MOUNT)

    deluser scu &> /dev/null
    addgroup -g $GROUPID scu
    adduser -u $USERID -G scu -D -s /bin/sh scu
fi


echo "Starting boot ..."
su-exec scu "$@"

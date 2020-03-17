#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "
WARNING="WARNING: [$(basename "$0")] "
ERROR="ERROR: [$(basename "$0")] "

# This entrypoint script:
#
# - Executes *inside* of the container upon start as --user [default root]
# - Notice that the container *starts* as --user [default root] but
#   *runs* as non-root user [scu]
#
echo "$INFO" "Entrypoint for stage ${SC_BUILD_TARGET} ..."
echo   User    :"$(id "$(whoami)")"
echo   Workdir :"$(pwd)"
echo   scuUser :"$(id scu)"


USERNAME=scu
GROUPNAME=scu

if [ "${SC_BUILD_TARGET}" = "development" ]
then
    echo "$INFO" "development mode detected..."
    # NOTE: expects docker run ... -v $(pwd):/devel/services/api-gateway
    DEVEL_MOUNT=/devel/services/api-gateway

    stat $DEVEL_MOUNT > /dev/null 2>&1 || \
        (echo "$ERROR" "You must mount '$DEVEL_MOUNT' to deduce user and group ids" && exit 1)

    USERID=$(stat --format=%u $DEVEL_MOUNT)
    GROUPID=$(stat --format=%g $DEVEL_MOUNT)
    GROUPNAME=$(getent group "${GROUPID}" | cut --delimiter=: --fields=1)

    if [ "$USERID" -eq 0 ]
    then
        echo "$WARNING" Folder mounted owned by root user... adding "$SC_USER_NAME" to root...
        adduser "${SC_USER_NAME}" root
    else
        # take host's credentials in scu
        if [ -z "$GROUPNAME" ]
        then
            echo "$INFO" mounted folder from "$USERID", creating new group my"${SC_USER_NAME}"
            GROUPNAME=my"${SC_USER_NAME}"
            addgroup --gid "$GROUPID" "$GROUPNAME"
            # change group property of files already around
            find / -path /proc -prune -group "$SC_USER_ID" -exec chgrp --no-dereference "$GROUPNAME" {} \;
        else
            echo "$INFO" "mounted folder from $USERID, adding ${SC_USER_NAME} to $GROUPNAME..."
            adduser "$SC_USER_NAME" "$GROUPNAME"
        fi

        echo "$INFO changing $SC_USER_NAME $SC_USER_ID:$SC_USER_ID to $USERID:$GROUPID"
        deluser "${SC_USER_NAME}" > /dev/null 2>&1
        if [ "$SC_USER_NAME" = "$GROUPNAME" ]
        then
            addgroup --gid "$GROUPID" "$GROUPNAME"
        fi
        adduser --disabled-password --gecos "" --uid "$USERID" --gid "$GROUPID" --shell /bin/sh "$SC_USER_NAME" --no-create-home
        # change user property of files already around
        find / -path /proc -prune -user "$SC_USER_ID" -exec chown --no-dereference "$SC_USER_NAME" {} \;
    fi

    echo "$INFO installing pythong dependencies..."
    cd services/api-gateway || exit 1
    pip install --no-cache-dir -r requirements/dev.txt
    cd - || exit 1
fi

if [ ${SC_BOOT_MODE} == "debug-ptvsd" ]
then
  # NOTE: production does NOT pre-installs ptvsd
  pip install --no-cache-dir ptvsd
fi


echo "$INFO Starting $* ..."
echo "  $SC_USER_NAME rights    : $(id "$SC_USER_NAME")"
echo "  local dir : $(ls -al)"

su --preserve-environment --command "export PATH=${PATH}; $*" "$SC_USER_NAME"

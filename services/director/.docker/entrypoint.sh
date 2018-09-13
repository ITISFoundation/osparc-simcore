#!/bin/sh

# This entrypoint script:
#
# - Executes with root privileges *inside* of the container upon start
# - Allows starting the container as root to perform some root-level operations at runtime
#  (e.g. on volumes mapped inside)
# - Notice that this way, the container *starts* as root but *runs* as scu (non-root user)
#
# See https://stackoverflow.com/questions/39397548/how-to-give-non-root-user-in-docker-container-access-to-a-volume-mounted-on-the


addgroup scu docker

if [[ ${RUN_DOCKER_ENGINE_ROOT} == "1" ]]
then
    echo "INFO: running from as root..."
    exec "$@"
else
    echo "INFO: running from as scu..."
    su-exec scu "$@"
fi

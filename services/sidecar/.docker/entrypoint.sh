#!/bin/sh

# This entrypoint script:
#
# - Executes with root privileges *inside* of the container upon start
# - Allows starting the container as root to perform some root-level operations at runtime
#  (e.g. on volumes mapped inside)
# - Notice that this way, the container *starts* as root but *runs* as scu (non-root user)
#
# See https://stackoverflow.com/questions/39397548/how-to-give-non-root-user-in-docker-container-access-to-a-volume-mounted-on-the


chown -R scu:scu /home/scu/input
chown -R scu:scu /home/scu/output
chown -R scu:scu /home/scu/log

#exec runuser --user scu "$@" <-- if ubuntu, use this
su-exec scu:scu "$@"

#!/bin/sh

#
# See https://stackoverflow.com/questions/39397548/how-to-give-non-root-user-in-docker-container-access-to-a-volume-mounted-on-the

# This container *starts* as root but *runs* as scu (non-root user)
chown -R scu:scu /home/scu/input
chown -R scu:scu /home/scu/output
chown -R scu:scu /home/scu/log

#exec runuser --user scu "$@" <-- this is the equivalent in ubuntu
su-exec scu:scu "$@"

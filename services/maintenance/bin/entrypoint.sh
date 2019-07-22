
#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'


echo "Booting application ..."
echo "  User    :`id $(whoami)`"
echo "  Workdir :`pwd`"
echo "  cmd : $@"

# Appends docker group if socket is mounted
DOCKER_MOUNT=/var/run/docker.sock

if [[ -e $DOCKER_MOUNT ]]
then
    GROUPID=$(stat -c %g $DOCKER_MOUNT)
    GROUPNAME=scdocker

    addgroup --gid $GROUPID $GROUPNAME &> /dev/null
    if [[ $? -gt 0 ]]
    then
        # if group already exists in container, then reuse name
        GROUPNAME=$(getent group ${GROUPID} | cut -d: -f1)
    fi
    adduser jovyan $GROUPNAME
fi

echo "su --preserve-environment --command $@ jovyan"
su --command "export PATH=${PATH}; $@" jovyan

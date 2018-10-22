#!/bin/bash
#
# Installs all python services in workspace's virtual environment and adds write permissions to the group
#
# - Expects a python virtual environment at $ROOTDIR/.venv that can be built using make .venv at $ROOTDIR
# - Temporary solution to issue #227 (or PR#220) since it  will create all .egg folders
# - This workaround is only for LINUX and must be applied once manually before running docker-compose in development mode
#

BASEDIR=$(dirname "$0")
ROOTDIR=$BASEDIR/..

# if .venv does not exists, notify user to use make .venv
source $ROOTDIR/.venv/bin/activate

pushd $ROOTDIR/services/web/server
pip3 install -r requirements/dev.txt
popd

pushd $ROOTDIR/services/director
pip3 install -r requirements/dev.txt
popd

pushd $ROOTDIR/services/sidecar
pip3 install -r requirements/dev.txt
popd

pushd $ROOTDIR/services/storage
pip3 install -r requirements/dev.txt
popd

#for package_dir in setup_dirs; do
#  pushd package_dir
#  pip3 install -r requirements/dev.txt
#  popd
#done

# find . -type d -name "*.egg*" | xargs chmod -R g+w
for a_folder in `find $ROOTDIR -type d \( -name "*.egg*" \)`
do
  chmod -R g+w $a_folder
done

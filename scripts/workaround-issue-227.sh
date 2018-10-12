#!/bin/bash
#
# Installs all python services in workspace's virtual environment
#
# - Expects a python virtual environment at $WORKDIR/.venv that can be built using make .venv at $WORKDIR
# - Temporary solution to issue #227 (or PR#220) since it  will create all .egg folders


BASEDIR=$(dirname "$0")
WORKDIR=$BASEDIR/..
SETUPDIRS =

# if .venv does not exists, notify user to use make .venv
source $WORKDIR/.venv/bin/activate

pushd $WORKDIR/services/web/server
pip3 install -r requirements/dev.txt
popd

pushd $WORKDIR/services/director
pip3 install -r requirements/dev.txt
popd

pushd $WORKDIR/services/sidecar
pip3 install -r requirements/dev.txt
popd

#for package_dir in setup_dirs; do
#  pushd package_dir
#  pip3 install -r requirements/dev.txt
#  popd
#done

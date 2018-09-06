#!/bin/sh
echo "activating python virtual env..."
source $HOME/.venv/bin/activate

if [[ ${DEBUG} == "1" ]]
then
  echo "INFO: Booting in development mode ..."
  echo "DEBUG: Director running as `id $(whoami)`"
  echo "DEBUG: Director running groups `groups`"
  
  echo "Installing director service ..."
  cd $HOME/services/director
  $PIP install --no-cache-dir -r requirements/dev.txt
  $PIP list
  cd $HOME
  simcore-service-director --loglevel=debug
else
  echo "INFO: Booting in production mode ..."
  simcore-service-director --loglevel=info
fi



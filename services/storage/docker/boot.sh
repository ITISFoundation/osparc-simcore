#!/bin/sh
echo "Activating python virtual env..."
source $HOME/.venv/bin/activate

if [[ ${DEBUG} == "1" ]]
then
  echo "Booting in development mode ..."
  echo "DEBUG: User    :`id $(whoami)`"
  echo "DEBUG: Workdir :`pwd`"

  cd $HOME/services/storage
  pip install -r requirements/dev.txt
  pip list

  cd $HOME/
  simcore-service-storage --config docker-dev-config.yaml
elif [[ ${DEBUG} == "2" ]]
then
  echo "Booting with debugger attached: https://docs.python.org/3.6/library/pdb.html#debugger-commands  ..."
  python -c "import pdb, simcore_service_storage.cli; pdb.run('simcore_service_storage.cli.main([\'-c\',\'docker-prod-config.yaml\'])')"
else
  echo "Booting in production mode ..."
  simcore-service-storage --config docker-prod-config.yaml
fi

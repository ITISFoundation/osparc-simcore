#!/bin/sh
source $HOME/.venv/bin/activate

if [[ ${DEBUG} == "1" ]]
then
  echo "Booting in development mode ..."
  echo "Installing director service ..."

  pip3 install --no-cache-dir -r requirements/dev.txt
  celery worker --app sidecar --concurrency 2 --loglevel=debug
else
  echo "Booting in production mode ..."
  celery worker --app sidecar --concurrency 2 --loglevel=info
fi

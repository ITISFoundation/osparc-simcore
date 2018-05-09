#!/bin/sh
source /home/app/venv/bin/activate

if [[ ${FLASK_DEBUG} == "1" ]]
then
  echo "Booting in development mode ..."
  exec python -m flask run --host=0.0.0.0 --port=8001
else
  echo "Booting in production mode ..."
  exec gunicorn -b :8001 --access-logfile - --error-logfile - director:APP
fi

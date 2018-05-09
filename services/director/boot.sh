#!/bin/sh
source /home/app/venv/bin/activate

if [[ ${FLASK_DEBUG} ]]
then
  # development
  exec python -m flask run --host=0.0.0.0 --port=8001
else
  # production
  exec gunicorn -b :8001 --access-logfile - --error-logfile - /source/director:app
fi

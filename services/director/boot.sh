#!/bin/sh
echo "activating python virtual env..."
source /home/scu/venv/bin/activate

if [[ ${DEBUG} == "1" ]]
then
  echo "Booting in development mode ..."
  echo "Installing director service ..."
  cd /home/scu/src
  /home/scu/venv/bin/pip install -r requirements-dev.txt
  cd ..
else
  echo "Booting in production mode ..."
fi

python -m director

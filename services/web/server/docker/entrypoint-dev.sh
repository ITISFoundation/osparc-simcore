#!/bin/sh

echo Running \'server "$@"\' ...

source ~/.venv/bin/activate
which python

# install
cd ~/source
pip install -r requirements-dev.txt

# creates sample data
# FIXME: create samples only if no data in-place
python src/server/utils/init_db.py

# runs server
python -m server --print-config
python -m server "$@"

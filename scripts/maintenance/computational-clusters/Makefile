.DEFAULT_GOAL := install

SHELL := /bin/bash

install:
	# creating python virtual environment
	@python3 -m venv .venv
	# activating python virtual environment
	@source .venv/bin/activate
	# installing python dependencies
	@.venv/bin/pip install --upgrade pip setuptools wheel
	@.venv/bin/pip install -r requirements.txt
	# now you can call the maintenance scripts
	# source .venv/bin/activate
	# e.g. ./osparc_clusters.py PATH/TO/REPO.CONFIG --ssh-key-path=PATH/TO/SSHKEY

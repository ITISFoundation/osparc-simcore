.DEFAULT_GOAL := install

SHELL := /bin/bash

install:
	# creating python virtual environment
	@uv venv .venv
	# activating python virtual environment
	@source .venv/bin/activate
	# installing python dependencies
	@uv pip install --upgrade pip setuptools wheel
	@uv pip install -r requirements.txt
	# now you can call the maintenance scripts
	# e.g. ./clean_projects_of_user https://osparc-master.speag.com USEREMAIL USERPASSWORD

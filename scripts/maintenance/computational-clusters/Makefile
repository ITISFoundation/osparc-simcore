.DEFAULT_GOAL := install

SHELL := /bin/bash

install:
	# creating python virtual environment
	@uv venv .venv
	# activating python virtual environment
	@source .venv/bin/activate
	# installing python dependencies
	@uv pip install --upgrade pip setuptools wheel
	@uv pip install -e .
	# now you can call the maintenance scripts
	# source .venv/bin/activate
	# autoscaled-monitor --deploy-config PATH/TO/REPO.CONFIG summary

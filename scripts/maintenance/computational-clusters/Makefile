.DEFAULT_GOAL := install

SHELL := /bin/bash

.venv:
	# creating python virtual environment
	@uv venv .venv
	# installing python dependencies
	@uv pip install --upgrade pip setuptools wheel


install: .venv
	# activating python virtual environment
	@source .venv/bin/activate
	# installing package
	@uv pip install .
	# now you can call the maintenance scripts
	# source .venv/bin/activate
	# autoscaled-monitor --deploy-config PATH/TO/REPO.CONFIG summary

install-dev: .venv
	# activating python virtual environment
	@source .venv/bin/activate
	# installing package
	@uv pip install -e .

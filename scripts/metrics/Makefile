.DEFAULT_GOAL := install

SHELL := /bin/bash

install:
	# creating python virtual environment
	@python3 -m venv .venv
	# installing python dependencies
	@.venv/bin/pip install --upgrade pip setuptools wheel
	@.venv/bin/pip install -r requirements.txt
	# activate the python virtual environment by running: ```source .venv/bin/activate```

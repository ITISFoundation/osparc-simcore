SHELL = /bin/bash

##
# Definitions.

.SUFFIXES:

# Python virtual environment
VENV_DIR = $(CURDIR)/../../.venv
OUTPUT_DIR = $(CURDIR)/out


##
# Targets .

.PHONE: up-swarm
up-swarm:
	docker swarm init
	docker stack deploy -c "$(OUTPUT_DIR)/docker-compose.yml"  services


.PHONE: down-swarm
down-swarm:
	docker swarm leave -f


$(VENV_DIR):
	@python3 -m venv "$(VENV_DIR)"
	@"$(VENV_DIR)/bin/pip3" install --upgrade pip wheel setuptools
	@"$(VENV_DIR)/bin/pip3" install pylint
	@echo "To activate the virtual environment, execute 'source env/bin/activate'"

.PHONY: venv
# venv – Create the virtual environment into venv folder
venv: $(VENV_DIR)

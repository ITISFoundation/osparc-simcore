.DEFAULT_GOAL := all

.PHONY: _check_venv_active
_check_venv_active:
	# Checking whether virtual environment was activated
	@python3 -c "import sys; assert sys.base_prefix!=sys.prefix"


.PHONY: install
install-dev install: _check_venv_active
	# installing webserver and requirements.txt
	@cd ./../../../services/web/server && make install-dev && cd -
	@pip install -r requirements.txt


.PHONY: all
all: _check_venv_active
	python openapi.py
